"""
SQLAlchemy ORM modellari
"""
from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """Bot foydalanuvchilari"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=False)
    is_blocked = Column(Boolean, default=False)          # botni bloklagan
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Munosabatlar
    broadcast_logs = relationship("BroadcastLog", back_populates="user", lazy="selectin")
    scheduled_logs = relationship("ScheduledSendLog", back_populates="user", lazy="selectin")

    def __repr__(self):
        return f"<User id={self.telegram_id} username={self.username}>"


class Movie(Base):
    """Kinolar katalogi"""
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # noyob kod
    title = Column(String(500), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False)       # arxiv kanal ID
    message_id = Column(BigInteger, nullable=False)       # kanal ichidagi xabar ID
    added_by = Column(BigInteger, nullable=True)          # qo'shgan admin ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_channel_message"),
    )

    def __repr__(self):
        return f"<Movie code={self.code} title={self.title}>"


class RequiredChannel(Base):
    """Majburiy obuna kanallari"""
    __tablename__ = "required_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, unique=True, nullable=False)
    channel_title = Column(String(255), nullable=True)
    invite_link = Column(String(500), nullable=False)     # foydalanuvchi uchun havola
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<RequiredChannel id={self.channel_id} title={self.channel_title}>"


class BotSetting(Base):
    """Bot umumiy sozlamalari (key-value)"""
    __tablename__ = "bot_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<BotSetting {self.key}={self.value}>"


class ScheduledMessage(Base):
    """Rejalashtirilgan xabarlar"""
    __tablename__ = "scheduled_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Xabar kontenti
    text = Column(Text, nullable=True)
    media_type = Column(String(20), nullable=True)        # photo/video/document/None
    media_file_id = Column(String(500), nullable=True)
    caption = Column(Text, nullable=True)
    parse_mode = Column(String(20), default="HTML")

    # Qabul qiluvchilar: "all" yoki user telegram_id
    recipient_type = Column(String(20), nullable=False, default="all")  # "all" | "user"
    recipient_id = Column(BigInteger, nullable=True)      # "user" bo'lsa to'ldiriladi

    # Jadval
    start_date = Column(String(10), nullable=False)       # YYYY-MM-DD
    send_time = Column(String(5), nullable=False)         # HH:MM
    duration_days = Column(Integer, nullable=False)       # necha kun
    timezone = Column(String(50), default="Asia/Tashkent")

    # Holat
    status = Column(String(20), default="active")         # active | paused | finished | cancelled
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Munosabatlar
    send_logs = relationship("ScheduledSendLog", back_populates="schedule", lazy="selectin")

    def __repr__(self):
        return f"<ScheduledMessage id={self.id} status={self.status}>"


class ScheduledSendLog(Base):
    """Rejalashtirilgan xabar yuborish jurnali (takrordan himoya)"""
    __tablename__ = "scheduled_send_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(Integer, ForeignKey("scheduled_messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    send_date = Column(String(10), nullable=False)        # YYYY-MM-DD
    status = Column(String(20), default="sent")           # sent | failed | skipped
    sent_at = Column(DateTime, default=datetime.utcnow)
    error_text = Column(Text, nullable=True)

    # Munosabatlar
    schedule = relationship("ScheduledMessage", back_populates="send_logs")
    user = relationship("User", back_populates="scheduled_logs")

    __table_args__ = (
        UniqueConstraint("schedule_id", "user_id", "send_date", name="uq_schedule_user_date"),
    )


class BroadcastLog(Base):
    """Ommaviy xabar yuborish jurnali"""
    __tablename__ = "broadcast_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    broadcast_id = Column(String(50), nullable=False, index=True)  # guruh ID (UUID)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), default="sent")           # sent | failed | blocked
    sent_at = Column(DateTime, default=datetime.utcnow)
    error_text = Column(Text, nullable=True)

    # Munosabat
    user = relationship("User", back_populates="broadcast_logs")
