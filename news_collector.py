import requests
from datetime import datetime, timedelta, timezone
import os
from email.utils import parsedate_to_datetime
import html
import json
import base64

NAVER_CLIENT_ID = os.environ['NAVER_CLIENT_ID']
NAVER_CLIENT_SECRET = os.environ['NAVER_CLIENT_SECRET']
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_CHANNEL = '모니터링-정보'
GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
GITHUB_REPO = os.environ['GITHUB_REPOSITORY']

KEYWORDS = ['닭가슴살', '랭킹닭컴', '다이어트', '식단', '하림', '한끼통살', '바르닭', '아임닭']

def get_posted_urls():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/posted_urls.json"
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        content = base64.b64decode(data['content']).decode('utf-8')
        return json.loads(content), data['sha']
    return {}, None

def clean_old_urls(posted_urls):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=2)
    return {
        url: ts for url, ts in posted_urls.items()
        if datetime.fromisoformat(ts) > cutoff
    }

def save_posted_urls(posted_urls, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/posted_urls.json"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
    }
    content_b64 = base64.b64encode(
        json.dumps(posted_urls, ensure_ascii=False, indent=2).encode('utf-8')
    ).decode('utf-8')
    data = {
        'message': f'Update posted URLs [{datetime.now(timezone.utc).isoformat()}]',
        'content': content_b64,
    }
    if sha:
        data['sha'] = sha
    response = requests.put(url, headers=headers, json=data)
    return response.status_code in [200, 201]

def search_naver_news(keyword):
    url = 'https://openapi.naver.com/v1/search/news.json'
    headers = {
        'X-Naver-Client-Id': NAVER_CLIENT_ID,
        'X-Naver-Client-Secret': NAVER_CLIENT_SECRET
    }
    params = {'query': keyword, 'display': 10, 'sort': 'date'}
    return requests.get(url, headers=headers, params=params).json()

def is_within_2_days(pub_date_str):
    try:
        pub_date = parsedate_to_datetime(pub_date_str)
        now = datetime.now(timezone.utc).astimezone(pub_date.tzinfo)
        return (now - pub_date) <= timedelta(days=2)
    except:
        return False

def clean_html(text):
    return html.unescape(text.replace('<b>', '').replace('</b>', ''))

def post_to_slack(message):
    url = 'https://slack.com/api/chat.postMessage'
    headers = {
        'Authorization': f'Bearer {SLACK_BOT_TOKEN}',
        'Content-Type': 'application/json; charset=utf-8'
    }
    result = requests.post(url, headers=headers, json={
        'channel': SLACK_CHANNEL,
        'text': message,
        'unfurl_links': False
    }).json()
    if not result.get('ok'):
        print(f"Slack error: {result.get('error')}")
    return result

def main():
    posted_urls, sha = get_posted_urls()
    posted_urls = clean_old_urls(posted_urls)
    newly_posted = {}

    for keyword in KEYWORDS:
        try:
            items = search_naver_news(keyword).get('items', [])
            new_articles = []

            for item in items:
                link = item['link'] if item['link'] else item['originallink']
                orig = item['originallink']

                if not is_within_2_days(item['pubDate']):
                    continue
                if link in posted_urls or orig in posted_urls:
                    continue

                new_articles.append({
                    'title': clean_html(item['title']),
                    'link': link,
                    'originallink': orig,
                    'pubDate': item['pubDate']
                })

            if new_articles:
                message = f"*[{keyword}] 최신 뉴스 ({len(new_articles)}건)*\n\n"
                for i, a in enumerate(new_articles, 1):
                    message += f"{i}. <{a['link']}|{a['title']}>\n"
                    message += f"   📅 {a['pubDate']}\n\n"
                post_to_slack(message)

                now_str = datetime.now(timezone.utc).isoformat()
                for a in new_articles:
                    newly_posted[a['link']] = now_str
                    newly_posted[a['originallink']] = now_str

                print(f"✅ {keyword}: {len(new_articles)}건 업로드")
            else:
                print(f"⏭️ {keyword}: 새 기사 없음")

        except Exception as e:
            print(f"❌ {keyword} 오류: {e}")

    if newly_posted:
        posted_urls.update(newly_posted)
        save_posted_urls(posted_urls, sha)
        print(f"✅ {len(newly_posted)}개 URL 저장 완료")

if __name__ == '__main__':
    main()
