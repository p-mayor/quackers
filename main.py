import json
import os
import random
from copy import deepcopy

import dotenv
import requests
import slack
from flask import Flask, request

# *********************************************
# EDIT HERE
# *********************************************

# map is in the following format:
# string name of originating channel: string name of coach channel
# example:
# 'joe-slackbot-testing': 'joe-slackbot-coaches'
channel_map = {
    'joe-slackbot-testing': 'joe-slackbot-coaches',
    'q1': 'q1-coaches',
}

# *********************************************
# DO NOT EDIT BEYOND THIS POINT
# *********************************************

dotenv.load_dotenv()
client = slack.WebClient(token=os.environ["BOT_USER_OAUTH_ACCESS_TOKEN"])
app = Flask(__name__)

modal_start = {
    "type": "modal",
    "title": {
        "type": "plain_text",
        "text": "QBert!",
        "emoji": True
    },
    "submit": {
        "type": "plain_text",
        "text": "Submit",
        "emoji": True
    },
    "close": {
        "type": "plain_text",
        "text": "Cancel",
        "emoji": True
    },
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": "The question was: {0}\nYour channel: {1}",
                "emoji": True
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "ml_input",
                "multiline": True
            },
            "label": {
                "type": "plain_text",
                "text": "What else should we know about the problem you're facing?"
            },
            "hint": {
                "type": "plain_text",
                "text": "Any context you can provide will help!"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "*NOTE*: Your question won't get sent to the coaches until you click submit!\nID: {}"
                }
            ]
        }
    ]
}


def get_coach_channel(c):
    result = channel_map[c]
    if not result:
        raise Exception("No matching channel found!")
    if not result.startswith("#"):
        result = "#{}".format(result)

    return result


def post_message_to_coaches(user, channel, question, info):
    ch = get_coach_channel(channel)
    message = (
        f"Received request for help from @{user} with the following info:\n\n"
        f"Question: {question}\n"
        f"Additional info: {info}\n\n"
        "React to this with :heavy_check_mark: if you'll reach out to the student"
        " and resolve."
    )

    client.chat_postMessage(
        channel=ch,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ],
        icon_emoji=":qbert:"
    )


def post_message_to_user(user, channel):
    emoji_list = [
        'party',
        'thepuff',
        'carlton',
        'fire',
        'spinning',
        'party-parrot',
        'heykirbyhey',
        'capemario'
    ]
    client.chat_postEphemeral(
        user="@{}".format(user),
        channel="#{}".format(channel),
        text=(
            "Thanks for reaching out! One of the coaches or facilitators will be"
            " with you shortly! :{}:".format(random.choice(emoji_list))
        )
    )


@app.route('/questionfollowup/', methods=['POST'])
def questionfollowup():
    data = request.form.to_dict()
    # the payload is a dict... as a string.
    data['payload'] = json.loads(data['payload'])

    # slack randomizes the block names. That means the location that the response will
    # be in won't always be the same. We need to pull the ID out of the rest of the
    # response before we go hunting for the data we need.
    # Bonus: every block will have an ID! Just... only one of them will be right.
    channel = None
    original_q = None
    addnl_info_block_id = None
    user_id = None

    for block in data['payload']['view']['blocks']:
        if block.get('type') == "input":
            addnl_info_block_id = block.get('block_id')
        if block.get('type') == "section":
            previous_data = block['text']['text'].split("\n")
            original_q = previous_data[0][previous_data[0].index(":") + 2:]
            channel = previous_data[1][previous_data[1].index(":") + 2:]
        if block.type == "context":
            user_id = block['elements']['text'].split(':')[2].strip()

    dv = data['payload']['view']

    additional_info = dv['state']['values'][addnl_info_block_id]['ml_input']['value']
    username = data['payload']['user']['username']

    post_message_to_coaches(
        user=username,
        channel=channel,
        question=original_q,
        info=additional_info
    )
    post_message_to_user(user=user_id, channel=channel)

    return ("", 200)


@app.route('/question/', methods=['POST'])
def question():
    data = request.form.to_dict()
    if trigger_id := data.get('trigger_id'):
        new_modal = deepcopy(modal_start)
        # stick the original question they asked and the channel they asked from
        # into the modal so we can retrieve it in the next section
        new_modal['blocks'][0]['text']['text'] = \
            modal_start['blocks'][0]['text']['text'].format(
                data.get('text'), data.get('channel_name')
            )

        new_modal['blocks'][4]['elements']['text'] = \
            modal_start['blocks'][4]['elements']['text'].format(data.get('user_id'))

        client.views_open(
            trigger_id=trigger_id,
            view=new_modal
        )
    # return an empty string per slack docs
    return ("", 200)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
