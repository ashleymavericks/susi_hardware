import threading

import pyaudio
import speech_recognition as sr
import os
import time

import speech.TTS as TTS
import susi_python as susi

from speech.SphinxRecognizer import SphinxRecognizer
from utils import websocket_utils
from utils.susi_config import config

recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = False
recognizer.energy_threshold = 1000

# TODO: Set parameters from environment variable.
# Currently, please set the variables for microphone initialization below manually.
# Refer following link for more information about parameters
# https://github.com/Uberi/speech_recognition/blob/master/reference/library-reference.rst#microphonedevice_index--none-sample_rate--16000-chunk_size--1024

# microphone = sr.Microphone(device_index=2, sample_rate=48000, chunk_size=2048)
microphone = sr.Microphone()


# Websocket Callbacks
def on_new_client(client, server):
    # server.send_message_to_all("Hey all, a new client has joined us")
    pass


def on_client_left(client, server):
    print("Client(%d) disconnected" % client['id'])


def on_message_received(client, server, message):
    # speak(message)
    reply = susi.answer_from_json(message)

    if 'answer' in reply.keys():
        print('Susi:' + reply['answer'])
        # Call flite tts to reply the response by Susi
        speak(reply['answer'])


websocketThread = websocket_utils.WebsocketThread(
    port=9001,
    fn_message_received=on_message_received,
    fn_client_left=on_client_left,
    fn_new_client=on_new_client
)


def speak(text):
    # Switch tts service here
    if config['default_tts'] == 'flite':
        TTS.speak_flite_tts(text)
    elif config['default_tts'] == 'watson':
        TTS.speak_watson_tts(text)


def ask_susi(input_query):
    # get reply by Susi
    reply = susi.ask(input_query)

    if 'answer' in reply.keys():
        print('Susi:' + reply['answer'])
        # Call festival tts to reply the response by Susi
        speak(reply['answer'])
    else:
        speak("I don't have an answer to this")


def recognize_audio(audio):
    if config['default_stt'] == 'google':
        return recognizer.recognize_google(audio)

    elif config['default_stt'] == 'watson':
        username = config['watson_speech_config']['username']
        password = config['watson_speech_config']['password']
        return recognizer.recognize_ibm(
            username=username,
            password=password,
            audio_data=audio)


def start_speech_recognition():
    try:
        print("Say something!")
        with microphone as source:
            audio = recognizer.listen(source, phrase_time_limit=5)
        print("Got it! Now to recognize it...")
        try:
            value = recognize_audio(audio)
            # websocketThread.send_to_all(value)
            print(value)
            ask_susi(value)

        except sr.UnknownValueError:
            print("Oops! Didn't catch that")
        except sr.RequestError as e:
            print("Uh oh! Couldn't request results from Google Speech Recognition service; {0}".format(e))

    except KeyboardInterrupt:
        pass


p = pyaudio.PyAudio()

stream = None


def open_stream():
    global stream
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=20480)
    stream.start_stream()
    print("--------------- RECOGNITION STARTED -----------------")


def close_stream():
    global stream
    stream.stop_stream()
    stream.close()


websocketThread.start()

open_stream()


# TODO: Decide threshold by a training based system.
# adjust threshold manually for now.
sphinxRecognizer = SphinxRecognizer(threshold=1e-30)

while True:
    buffer = stream.read(20480, exception_on_overflow=False)
    if buffer:
        if sphinxRecognizer.is_recognized(buffer):
            print("hotword detected")
            # play the detection bell
            os.system('play extras/detection-bell.wav &')
            close_stream()
            start_speech_recognition()
            open_stream()

    else:
        break

websocketThread.join()
