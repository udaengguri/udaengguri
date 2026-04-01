import requests
from datetime import datetime, timedelta, timezone
import os
from email.utils import parsedate_to_datetime
import html

NAVER_CLIENT_ID = os.environ['NAVER_CLIENT_ID']
NAVER_CLIENT_SECRET = os.environ['NAVER_CLIENT_SECRET']
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_CHANNEL = '모니터링-정보'

KEYWORDS = ['닭가슴살', '랭킹닭컴', '다이어트', '식단', '하림', '한끼통살', '바르닭', '아임닭']

def search_naver_news(keyword):
    url = 'https://openapi.naver.com/v1/search/news.json'
    headers = {
        'X-Naver-Client-Id': NAVER_CLIENT_ID,
        'X-Naver-Client-Secret': NAVER_CLIENT_SECRET
    }
    params = {
        'query': keyword,
        'display': 10,
        'sort': 'date'
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()

def is_within_2_days(pub_date_str):
    try:
        pub_date = parsedate_to_datetime(pub_date_str)
        now = datetime.now(timezone.utc).astimezone(pub_date.tzinfo)
        return (now - pub_date) <= timedelta(days=2)
    except:
        return False

def clean_html(text):
    text = text.replace('<b>', '').replace('</b>', '')
    return html.unescape(text)

def post_to_slack(message):
    url = 'https://slack.com/api/chat.postMessage'
    headers = {
        'Authorization': f'Bearer {SLACK_BOT_TOKEN}',
        'Content-Type': 'application/json; charset=utf-8'
    }
    data = {
        'channel': SLACK_CHANNEL,
        'text': message,
        'unfurl_links': False
    }
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    if not result.get('ok'):
        print(f"Slack error: {result.get('error')}")
    return result

def main():
    for keyword in KEYWORDS:
        try:
            result = search_naver_news(keyword)
            items = result.get('items', [])

            recent_articles = []
            for item in items:
                if is_within_2_days(item['pubDate']):
                    title = clean_html(item['title'])
                    link = item['link'] if item['link'] else item['originallink']
                    recent_articles.append({
                        'title': title,
                        'link': link,
                        'pubDate': item['pubDate']
                    })

            if recent_articles:
                message = f"*[{keyword}] 최신 뉴스 ({len(recent_articles)}건)*\n\n"
                for i, article in enumerate(recent_articles, 1):
                    message += f"{i}. <{article['link']}|{article['title']}>\n"
                    message += f"   📅 {article['pubDate']}\n\n"
                post_to_slack(message)
                print(f"✅ {keyword}: {len(recent_articles)}건 업로드 완료")
            else:
                print(f"⏭️ {keyword}: 최근 2일 이내 기사 없음")

        except Exception as e:
            print(f"❌ {keyword} 오류: {e}")

if __name__ == '__main__':
    main()
