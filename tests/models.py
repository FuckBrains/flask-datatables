import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import relationship, sessionmaker, backref

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    full_name = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)



class Address(Base):
    __tablename__ = 'addresses'

    id = Column(Integer, primary_key=True)
    description = Column(Text)
    user_id = Column(Integer, ForeignKey('users.id'))

    user = relationship("User", backref=backref("address", uselist=False))

    def __repr__(self):
        return "{}".format(self.description)
