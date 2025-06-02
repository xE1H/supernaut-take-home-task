"""
Configuration settings for the app
"""


class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///supernaut.db'  # sqlite here for simplicity
    SQLALCHEMY_TRACK_MODIFICATIONS = False
