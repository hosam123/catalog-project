from flask import Flask, render_template
from flask import request, redirect, url_for, jsonify, flash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, League, Team, User

# imports for Authentication & Authorization
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests


# prepare sqlalchemy session for database operations
engine = create_engine('sqlite:///teams.db')
Base.metadata.create_all(engine)
DBSession = sessionmaker(bind=engine)
session = DBSession()

# create new app
app = Flask(__name__)
app.secret_key = ''.join(random.choice(
    string.ascii_uppercase + string.digits) for i in range(48))


def getUserdId(name, mail):
    try:
        user = session.query(User).filter_by(mail=mail).one()
    except:
        user = User(name=name, mail=mail)
        session.add(user)
        session.commit()
        user = session.query(User).filter_by(mail=mail).one()
    return user.id


# default route for logging page
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for i in range(32))
    login_session['state'] = state
    return render_template('login_page.html', STATE=login_session['state'])


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        print('hi')
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    clientId = ('617260085365-f1mpj9c5b5eqggvu87hb3adisje2sidt' +
                '.apps.googleusercontent.com')
    if result['issued_to'] != clientId:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print("Token's client ID does not match app's.")
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'),
            200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    login_session['user_id'] = getUserdId(login_session['username'],
                                          login_session['email'])

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ''' " style = "width: 300px;
    height: 300px;border-radius: 150px;-webkit-border-radius: 150px;
    -moz-border-radius: 150px;"> '''
    flash("you are now logged in as %s" % login_session['username'])
    print("done!")
    return output


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        print('Access Token is None')
        response = make_response(json.dumps(
            'Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print('In gdisconnect access token is %s', access_token)
    print('User name is: ')
    print(login_session['username'])
    url = ('https://accounts.google.com/o/oauth2/revoke?token=%s' %
           login_session['access_token'])
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print('result is ')
    print(result)
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(json.dumps(
            'Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# default route for main page
@app.route('/')
@app.route('/index')
def mainPage():
    logged = 'username' in login_session
    leagues = session.query(League).all()
    latest_teams = session.query(Team).order_by(Team.id.desc()).limit(2)
    return render_template('main.html', leagues=leagues,
                           teams=latest_teams, logged=logged)


# api endpoints responds with json format

@app.route('/json')
def jsonAllTeams():
    teams = session.query(Team).all()
    return(jsonify(AllTeams=[team.serialize for team in teams]))


@app.route('/team/<int:team_id>/json')
def jsonTeam(team_id):
    team = session.query(Team).filter_by(id=team_id).first()
    return(jsonify(team.serialize))


# league page
@app.route('/league/<int:league_id>')
def leaguePage(league_id):
    leagues = session.query(League).all()
    league = session.query(League).filter_by(id=league_id).first()
    teams = session.query(Team).filter_by(league_id=league_id).all()
    print(league.name)
    return render_template('league_page.html', leagues=leagues,
                           league=league, teams=teams)


# team page
@app.route('/team/<int:team_id>')
def teamPage(team_id):
    logged = 'username' in login_session
    team = session.query(Team).filter_by(id=team_id).first()
    return render_template('team_page.html', logged=logged, team=team)


# page for adding new team
@app.route('/new_team', methods=['GET', 'POST'])
def newTeam():
    authenticated = 'username' in login_session
    if not authenticated:
        return redirect(url_for('showLogin'))

    if request.method == 'POST':
        new_team = Team(name=request.form['title'],
                        user_id=login_session['user_id'],
                        info=request.form['info'], league_id=int(
            request.form['league']))
        session.add(new_team)
        session.commit()
        return redirect(url_for('mainPage'))
    else:
        leagues = session.query(League).all()
        return render_template('new_team.html', leagues=leagues)


# page for editing team
@app.route('/edit_team/<int:team_id>', methods=['GET', 'POST'])
def editTeam(team_id):
    authenticated = 'username' in login_session
    team = session.query(Team).filter_by(id=team_id).first()
    authorized = login_session['user_id'] == team.user_id
    if not authenticated:
        return redirect(url_for('showLogin'))
    if not authorized:
        return "<h1> this team added by another user !!!! </h1>"
    if request.method == 'POST':
        team.name = request.form['title']
        team.info = request.form['info']
        team.league_id = int(request.form['league'])
        session.add(team)
        session.commit()
        return redirect(url_for('teamPage', team_id=team_id))
    else:
        leagues = session.query(League).all()
        return render_template('edit_team.html', leagues=leagues, team=team)


# page for deleting team
@app.route('/delete_team/<int:team_id>', methods=['GET', 'POST'])
def deleteTeam(team_id):
    authenticated = 'username' in login_session
    team = session.query(Team).filter_by(id=team_id).first()
    authorized = login_session['user_id'] == team.user_id
    if not authenticated:
        return redirect(url_for('showLogin'))
    if not authorized:
        return "<h1> this team added by another user !!!! </h1>"
    if request.method == 'POST':
        team = session.query(Team).filter_by(id=team_id).first()
        session.delete(team)
        session.commit()
        return redirect(url_for('mainPage'))
    else:
        return render_template('delete_team.html', team=team)


# now it's time to run the application
if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
