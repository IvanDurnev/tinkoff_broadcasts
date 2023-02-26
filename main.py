from flask import Flask, send_from_directory
import requests
import os
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = Flask(__name__)


@app.get('/')
def index():
    calendar_id = '3e9ee0552d3eaa809af571c2c4f90705692c803cd938821238353e43a53fe6cb@group.calendar.google.com'
    tinkoff_list = requests.get('https://tinkoff-backend.prod.watchers.io/room/premade')
    # tinkoff_list = requests.get('http://127.0.0.1:5000/events')
    google_list = get_events(calendar_id=calendar_id)

    # создание событий, которые есть в списке Тинька, но нет в списке Гугла
    for event in tinkoff_list.json():
        internal_id = str(event['id'])
        if not id_in_json(internal_id, google_list, source='google'):
            create_calendar_event(calendar_id=calendar_id,
                                  internal_id=internal_id,
                                  title=event['name'],
                                  start=event['startTime'],
                                  end=event['endTime'],
                                  pic=event['pic'])
    for event in google_list:
        internal_id = int(event['extendedProperties']['private']['my_internal_id'])
        if id_in_json(internal_id, tinkoff_list.json(), source='tinkoff'):
            # если событие есть и в Тиньке и в Гугле, обновляем данные в Гугле
            # берем событие из Тинька
            for source_event in tinkoff_list.json():
                if source_event['id'] == int(internal_id):
                    edit_calendar_event(calendar_id=calendar_id,
                                        event_id=event['id'],
                                        title=source_event['name'],
                                        start=source_event['startTime'],
                                        end=source_event['endTime'],
                                        pic=source_event['pic'])
        else:
            # если событие есть в Гугле, но нет в Тиньке - удаляем из гугла
            del_calendar_event(calendar_id=calendar_id,
                               event_id=event['id'])

    return tinkoff_list.json()


@app.get('/events')
def test_events():
    return send_from_directory(directory=os.path.join('test'), path='events.json')


def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        os.path.join('credentials', 'tinkoff-broadcasts-ec89a5eff9a3.json'),
        scopes=['https://www.googleapis.com/auth/calendar']
    )

    # Создаем сервис Google Calendar
    service = build('calendar', 'v3', credentials=creds)
    return service


def get_events(calendar_id):
    service = get_calendar_service()

    # Определяем интервал времени для получения событий
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=now,
        maxResults=100,
        singleEvents=True,
        orderBy='startTime',
    ).execute()
    events = events_result.get('items', [])

    return events


def create_calendar_event(calendar_id, internal_id, title, start, end, pic=None):
    service = get_calendar_service()
    event = {
        'summary': title,
        'description': f'<img src="{pic}" />' if pic else '',
        'start': {
            'dateTime': start,
            'timeZone': 'Europe/Moscow',
        },
        'end': {
            'dateTime': end,
            'timeZone': 'Europe/Moscow',
        },
        'extendedProperties': {
            'private': {
                'my_internal_id': internal_id,
            },
        },
    }

    try:
        # Создаем новое событие в календаре
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event,
        ).execute()
        print(f"Событие '{created_event}' успешно создано")
    except HttpError as error:
        print(f"Ошибка при создании события: {error}")


def edit_calendar_event(calendar_id, event_id, title, start, end, pic=None):
    service = get_calendar_service()

    # Получаем информацию о событии
    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

    # Изменяем время начала и конца события
    event['summary'] = title
    event['start']['dateTime'] = start
    event['end']['dateTime'] = end
    event['description'] = f'<img src="{pic}" />' if pic else ''

    try:
        # Обновляем событие в календаре
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
        ).execute()
        print(f"Событие '{updated_event['summary']}' успешно изменено")
    except HttpError as error:
        print(f"Ошибка при изменении события: {error}")


def del_calendar_event(calendar_id, event_id):
    service = get_calendar_service()
    try:
        # Удаляем событие
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        print(f'Событие {event_id} успешно удалено.')
    except HttpError as error:
        print(f'Произошла ошибка: {error}')


def id_in_json(value, data: json, source):
    if source == 'tinkoff':
        return True if value in [i['id'] for i in data] else False
    if source == 'google':
        return True if value in [i['extendedProperties']['private']['my_internal_id'] for i in data] else False
