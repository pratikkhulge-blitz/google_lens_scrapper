import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Optional: Use environment variable for security
slack_token = os.getenv("SLACK_BOT_TOKEN")
channel_name = "#test-alerts"

def send_custom_msg(msg: str) -> str:
    if not slack_token or not channel_name:
        return 'Slack configuration missing.'

    client = WebClient(token=slack_token)
    
    try:
        response = client.chat_postMessage(
            channel=channel_name,
            text=msg,
            username="Google Lens Bot"
        )
        if response["ok"]:
            return 'Notified!'
        else:
            return 'Slack API response not OK.'

    except SlackApiError as e:
        return f"Slack notification failed: {e.response['error']}"
    except Exception as e:
        return 'Slack notification failed with unknown error.'
