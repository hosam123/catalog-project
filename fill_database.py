from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, League

engine = create_engine('sqlite:///teams.db')
Base.metadata.create_all(engine)
DBSession = sessionmaker(bind=engine)
session = DBSession()


# fill the database with your leagues
n = int(raw_input("Enter number of leagues : "))
for i in range(n):
    league_name = raw_input("enter league name : ")
    templeague = League(name=league_name)
    session.add(templeague)

session.commit()
print("leagues added !!")
