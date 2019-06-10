
# 並列処理
import threading
import os
import json
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime as dt
import datetime
import requests
from decimal import Decimal
import random

from requests_oauthlib import OAuth1Session  # OAuthのライブラリの読み込み

# ネガポジ閾値
negpos_threshold = int(os.environ["negpos_threshold"])
# Slack通知先
slack_room = os.environ["slack_chanel"]

# twitterAPIアクセストークン
CK = os.environ["twitter_CK"]
CS = os.environ["twitter_CS"]
AT = os.environ["twitter_AT"]
ATS = os.environ["twitter_ATS"]

NLP_Key = os.environ["NLP_Key"]

MONTH_LUT = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
}

def lambda_function(event, content):
    thread_1 = threading.Thread(target=return_200)
    thread_2 = threading.Thread(target=main_func(event, content))
    return 0

# slackにとりあえず200を返す
def return_200():
    print("prodess kill")
    return 0

# 基準日からのツイートデータを取得する
def get_tweet_data(ref_day):
    try:
        dynamoDB = boto3.resource("dynamodb")
        table = dynamoDB.Table("twitter_negpos")  # DynamoDBのテーブル名

        dynamo_data = table.query(
            KeyConditionExpression=Key("tweet_time").gt(ref_day)
        )

        return dynamo_data
    except Exception as e:
        print(e)

def date_translate(date):
    pre_date = date.split(' ')
    y = pre_date[-1]
    m = MONTH_LUT[pre_date[1]]
    d = pre_date[2]
    time = pre_date[3]
    res_date = '{}-{}-{} {}'.format(y, m, d, time)
    return res_date

def main_func(event, content):
    twitter = OAuth1Session(CK, CS, AT, ATS)  #認証処理
    query = os.environ["query"]
    # twitter検索結果取得エンドポイント
    url = 'https://api.twitter.com/1.1/search/tweets.json'

    # ランサーズが含まれる昨日からのツイートを取得する
    since = dt.now() - datetime.timedelta(days=1)
    query += " since:" + since.strftime("%Y-%m-%d")
    res = twitter.get(url, params={'q': query})
    res_status_code = 200

    if res_status_code == 200:
        res_text = json.loads(res.text)
        # print(res_text)

        #NLPAPI
        nlp_url = 'https://language.googleapis.com/v1/documents:analyzeSentiment?key=' + NLP_Key

        header = {'Content-Type': 'application/json'}
        body = {
            "document": {
                "type": "PLAIN_TEXT",
                "language": "ja",
                "content" : ""
            },
            "encodingType": "UTF8"
        }
        # response = requests.post(nlp_url, headers=header, json=body).json()
        # print(response)

        # 基準となる日
        ref_day = Decimal(since.timestamp())
        print(ref_day)

        dynamo_data = get_tweet_data(ref_day)

        # pos_tweet = ""
        # neg_tweet = ""
        print(dynamo_data)

        # # 検知済みのツイートを弾く
        for tweet in res_text['statuses']:
        #     # if tweet['id_str'] in dynamo_data:
        #     #     continue
        #     # この下でgoogle NLP叩く
            body['document']['content'] = tweet['text']
            print(body)
            response = requests.post(nlp_url, headers=header, json=body).json()

            print(response)
            score = response['documentSentiment']['score']
            abs_score = response['documentSentiment']['magnitude']
            print(score)
            tweet_link = "https://twitter.com/" + tweet['user']['screen_name'] + "/status/" + tweet['id_str']

        #     if score > 1:
        #         pos_tweet += tweet['text']
        #         pos_tweet += tweet_link + "\n\n"

        #     if score < -1:
        #         neg_tweet += tweet['text']
        #         neg_tweet += tweet_link

            # ツイートデータを保存する
            try:
                dynamoDB = boto3.resource("dynamodb")
                table = dynamoDB.Table("twitter_negpos")  # DynamoDBのテーブル名

                # print(tweet)
                preform_date = dt.strptime(date_translate(tweet['created_at']), '%Y-%m-%d %H:%M:%S')
                tweet_time = Decimal(preform_date.timestamp())

                # 昨日からのツイートデータをとってくる
                res = table.put_item(
                    Item={
                        "tweet_id": str(tweet['id_str']),
                        "search_query": "ランサーズ",
                        'abs_score' :
                        "negpos": Decimal(str(score)),
                        "tweet_text": tweet['text'],
                        "tweet_user": tweet['user']['screen_name'],
                        "tweet_time": tweet_time,
                        "tweet_link": tweet_link
                    }
                )
            except Exception as e:
                print(e)

        # post_text = "@urara.masahiro\n\n" + "■ポジティブ\n" + pos_tweet + "\n\n■ネガティブ\n" + neg_tweet

        # SLACK_WEBHOOK = "https://hooks.slack.com/services/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"
        # # ツイートデータをslackに投げる
        # payload_dic = {
        #     "text": post_text,
        #     "username": "twitterネガポジ分析",
        #     "channel": "#gr_cc_twitter対応",  # も必要
        # }

        # r = requests.post(SLACK_WEBHOOK, data=json.dumps(payload_dic))

    return 0
