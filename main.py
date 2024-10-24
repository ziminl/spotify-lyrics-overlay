from syrics.api import Spotify
import spotipy
import spotipy.util as util
import configparser
from time import sleep
import sys
from threading import Thread
from multiprocessing import Process
import asyncio

from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *

class Worker(QThread):
  update_signal = Signal(str)

  def run(self):
    while True:
      track_info = sp2.current_playback()

      if track_info is not None:
        is_playing = track_info['is_playing']
        progress_ms = track_info['progress_ms']
        device = track_info['device']['name']
        song = track_info['item']['name']
        song_id = track_info['item']['id']
        artist = track_info['item']['artists'][0]['name']
        album = track_info['item']['album']['name']

        song = song.replace('’', '\'')
        artist = artist.replace('’', '\'')

        is_daemon = True
        sleep_time = 10.0
        idx = 0
        data = sp1.get_lyrics(song_id)
        try:
          lyrics = data['lyrics']['lines']
        except Exception as e:
          lyrics = []

        while is_daemon:
          track_info = sp2.current_playback()
          is_playing = track_info['is_playing']
          progress_ms = track_info['progress_ms']

          while is_playing:
            if is_daemon == False:
              break

            try:
              if len(lyrics) == 0:
                self.update_signal.emit("해당 곡의 가사가 등록되어 있지 않습니다.")
                break
            except Exception as e:
              pass
            if int(lyrics[idx]['startTimeMs']) < int(progress_ms):
              self.update_signal.emit(lyrics[idx]['words'])
              idx += 1
              if idx == len(lyrics):
                break
              continue
            elif lyrics[idx]['words'] == '':
              current_line = "  "
              self.update_signal.emit(current_line)
              idx += 1
              if idx == len(lyrics):
                break
              sleep((int(lyrics[idx]['startTimeMs']) - int(progress_ms)) / 1000)
            else:
              if is_playing:
                current_line = lyrics[idx]['words']
                self.update_signal.emit(current_line)
                idx += 1
                if idx == len(lyrics):
                  break
                sleep((int(lyrics[idx]['startTimeMs']) - int(progress_ms)) / 1000)
              else:
                self.update_signal.emit("Paused")
                sleep(sleep_time)
            track_info = sp2.current_playback()
            if track_info is not None:
              _song_id = track_info['item']['id']
              is_playing = track_info['is_playing']
              progress_ms = track_info['progress_ms']

              if is_playing and _song_id == song_id:
                data = sp1.get_lyrics(song_id)
                lyrics = data['lyrics']['lines']

                song_id = _song_id
                self.update_signal.emit("song_change")
              else:
                break
            else:
              break
          if is_daemon and track_info is not None:
            if not is_playing:
              current_line = "Paused"
              self.update_signal.emit(current_line)
              sleep(sleep_time)
            else:
              break
          else:
            current_line = ""
            break
      else:
        current_line = "Spotify is sleeping"
        self.update_signal.emit(current_line)
      sleep(1)

class LyricsOverlay(QMainWindow):
  def __init__(self):
    super(LyricsOverlay, self).__init__()
    self.w, self.h = 320, 120
    
    self.label_idx = 0
    self.is_dragging = False
    self.drag_start_position = QPoint()

    self.worker = Worker()
    self.worker.update_signal.connect(self.update_label)

    self.init_ui()
    self.worker.start()
    
  def init_ui(self):
    self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)

    self.setFixedSize(self.w, self.h)
    self.setWindowOpacity(0.7)
    self.setAttribute(Qt.WA_TranslucentBackground)

    self.round_widget = QWidget(self)
    self.round_widget.resize(self.w, self.h)

    self.round_widget.setStyleSheet(
      """
      background:rgb(3, 3, 3);
      border-radius: 10px;
      """
    )

    self.lyrics_label0 = QLabel("<p style='color: white; text-align: center'></p>")
    self.font = self.lyrics_label0.font()
    self.font.setPointSize(15)
    self.lyrics_label0.setFont(self.font)

    self.lyrics_label1 = QLabel("<p style='color: white; text-align: center'></p>")
    self.font = self.lyrics_label1.font()
    self.font.setPointSize(15)
    self.lyrics_label1.setFont(self.font)

    self.layout = QVBoxLayout()
    self.layout.addWidget(self.lyrics_label0)
    self.layout.addWidget(self.lyrics_label1)

    self.widget = QWidget()
    self.widget.setLayout(self.layout)
    self.setCentralWidget(self.widget)

  def update_label(self, text):
    if text == "song_change":
      self.lyrics_label0.setText(f"<p style='color: white; text-align: center; font-size: 15px;'></p>")
      self.lyrics_label1.setText(f"<p style='color: white; text-align: center; font-size: 15px;'></p>")
      self.label_idx = 0
      pass
    if text == "해당 곡의 가사가 등록되어 있지 않습니다." or text == "Spotify is sleeping":
      self.lyrics_label0.setText(f"<p style='color: white; text-align: center; font-size: 15px;'>{text}</p>")
      self.lyrics_label1.setText(f"<p style='color: white; text-align: center; font-size: 15px;'></p>")
      return
    if self.label_idx == 0:
      self.label_idx = 1
      self.lyrics_label0.setText(f"<p style='color: white; text-align: center; font-size: 15px;'>{text}</p>")
    elif self.label_idx == 1:
      self.label_idx = 0
      self.lyrics_label1.setText(f"<p style='color: white; text-align: center; font-size: 15px;'>{text}</p>")

  def mousePressEvent(self, event):
    if event.button() == Qt.LeftButton:
      self.is_dragging = True
      self.drag_start_position = event.globalPos() - self.pos()
      event.accept()

  def mouseMoveEvent(self, event):
    if self.is_dragging:
      self.move(event.globalPos() - self.drag_start_position)
      event.accept()

  def mouseReleaseEvent(self, event):
    if event.button() == Qt.LeftButton:
      self.is_dragging = False
      event.accept()

def setup():
  config = configparser.ConfigParser()
  config.read('./config.ini')

  name = config['client']['name']
  client_id = config['client']['client_id']
  client_secret = config['client']['client_secret']
  scope = config['oauth']['scope']
  redirect_uri = config['oauth']['redirect_uri']
  sp_dc = config['oauth']['sp_dc']

  token = util.prompt_for_user_token(
          username=name,
          scope=scope,
          client_id=client_id,
          client_secret=client_secret,
          redirect_uri=redirect_uri)

  app_setting = {
    'app_name': config['app']['app_name'],
    'app_icon': config['app']['app_icon']
  }

  sp1 = Spotify(sp_dc)
  sp2 = spotipy.Spotify(auth=token)

  return app_setting, sp1, sp2

if __name__ == "__main__":
  app_setting, sp1, sp2 = setup()

  app = QApplication(sys.argv)
  app.setApplicationDisplayName(app_setting['app_name'])
  app.setWindowIcon(QIcon(app_setting['app_icon']))

  overlay = LyricsOverlay()
  overlay.show()
  app.exec()
