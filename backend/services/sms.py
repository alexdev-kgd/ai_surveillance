from infobip_api_client.api_client import ApiClient, Configuration
from infobip_api_client.models import (
    SmsDestination,
    SmsMessage,
    SmsMessageContent,
    SmsRequest,
    SmsResponse,
    SmsTextContent,
)
from infobip_api_client.api.sms_api import SmsApi
from infobip_api_client.exceptions import ApiException

client_config = Configuration(
    host="k9q3p1.api.infobip.com",
    api_key="fef0fbdfc051f479461117021c162475-67abec5a-0b31-4534-9e9a-7a59c0eca704",
)

api_client = ApiClient(client_config)
api_instance = SmsApi(api_client)


def send_sms_notification(event_desc: str):
    message_text = f"Обнаружена подозрительная активность. Событие: {event_desc}"
    print(f"[SMS] Уведомление: {event_desc}")

    sms_request = SmsRequest(
        messages=[
            SmsMessage(
                destinations=[SmsDestination(to="79506781834")],
                sender="InfoSMS",
                content=SmsMessageContent(
                    actual_instance=SmsTextContent(text=message_text)
                ),
            )
        ]
    )

    try:
        api_response: SmsResponse = api_instance.send_sms_messages(
            sms_request=sms_request
        )
        print(api_response)
    except ApiException:
        print("Ошибка при отправке SMS-сообщения.")
