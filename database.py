import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, func
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

url = os.getenv("DATABASE_URL", "sqlite:///nova.db")
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)  # paksa driver psycopg2

if url.startswith("postgresql"):
    engine = create_engine(url, poolclass=NullPool, pool_pre_ping=True)  # aman untuk serverless
else:
    engine = create_engine(url, connect_args={"check_same_thread": False})

Session = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    player_id = Column(String(12), unique=True, nullable=False, index=True)  # ID angka publik, sama pola dengan NOVA WAWA
    username = Column(String(30), unique=True, nullable=False, index=True)   # @handle, unik, dipakai untuk login & profil
    full_name = Column(String(100), nullable=False)
    birth_year = Column(Integer, nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    bio = Column(String(150), default="")
    avatar = Column(Text, default="")  # data URL kecil, atau URL Cloudinary
    created_at = Column(DateTime, server_default=func.now())

    def public(self, mine=False):
        o = {"player_id": self.player_id, "username": self.username, "full_name": self.full_name,
             "bio": self.bio or "", "avatar": self.avatar or ""}
        if mine:
            o["birth_year"] = self.birth_year
        return o


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    owner = Column(String(12), nullable=False, index=True)   # player_id pembuat
    kind = Column(String(5), nullable=False, default="image")  # image | video
    media = Column(Text, nullable=False)                      # data URL (atau URL Cloudinary nanti)
    caption = Column(String(2200), default="")
    created_at = Column(DateTime, server_default=func.now(), index=True)


class Like(Base):
    __tablename__ = "likes"
    post_id = Column(Integer, primary_key=True)
    player_id = Column(String(12), primary_key=True)
    created_at = Column(DateTime, server_default=func.now())


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, nullable=False, index=True)
    player_id = Column(String(12), nullable=False, index=True)
    body = Column(String(500), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Follow(Base):
    __tablename__ = "follows"
    follower = Column(String(12), primary_key=True)  # yang mengikuti
    target = Column(String(12), primary_key=True)    # yang diikuti
    created_at = Column(DateTime, server_default=func.now())


class RateHit(Base):  # percobaan login/daftar, untuk pembatas laju (sama pola dengan NOVA WAWA)
    __tablename__ = "rate_hits"
    id = Column(Integer, primary_key=True)
    key = Column(String(120), nullable=False, index=True)
    ts = Column(DateTime, nullable=False, index=True)


def init_db():
    Base.metadata.create_all(engine)
