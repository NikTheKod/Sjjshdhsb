from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import random
import string

engine = create_engine('sqlite:///bot_database.db')
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Purchase(Base):
    __tablename__ = 'purchases'
    id = Column(Integer, primary_key=True)
    purchase_id = Column(String, unique=True)
    user_id = Column(Integer)
    username = Column(String, nullable=True)
    stars_amount = Column(Integer)
    price_rub = Column(Float)
    telegram_payment_id = Column(String, nullable=True)
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

def generate_purchase_id():
    return f"PUR-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"

Base.metadata.create_all(engine)
