from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    alerts = relationship("Alert", back_populates="user")

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    stock_symbol = Column(String)
    target_price = Column(Float)
    user = relationship("User", back_populates="alerts")

engine = create_engine("sqlite:///alerts.db")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
