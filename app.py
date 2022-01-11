from flask import Flask, redirect, render_template, request
import psycopg2, json
from datetime import datetime
from decouple import config

app = Flask(__name__)


def establish_db_connection():
    # not preferred method to use pycog directly. good enough for first step
    # preferred method is SQLAlchemy
    conn = psycopg2.connect(
        user=config('DB_USER'),
        password=config('PASSWORD'),
        host=config('HOST'),
        database=config('DB_NAME'),
        port=config('PORT')
    )
    return conn


@app.route('/api/url-reader/gamescorekeeper/', methods=('GET', 'POST'))
def gameScoreKeeper():
    con = establish_db_connection()
    status = None
    if request.method == 'POST':
        # get parameter from the form
        twitch_url = request.form['twitch_url']
        with con.cursor() as cur:
            # to avoid sql injections parametrised/compiled query
            cur.execute(
                f"INSERT INTO api_gsk_fifa (twitch_url, added_on_to_db) VALUES ('{twitch_url}', '{int(datetime.now().timestamp())}')",
            )
            # commit transactions
            con.commit()
        status = True
    con.close()
    return render_template('twitch_url.html', status=status)


@app.route('/api/duel/supported_games/', methods=('GET',))
def get_duel_supported_games():
    con = establish_db_connection()
    status = None
    if request.method == "GET":
        with con.cursor() as cur:
            cur.execute("select game_id, game_name from api_duel_supportedgames")
        results = json.dumps({x[0]: x[1] for x in cur.fetchall()})
    else:
        results = json.dumps({})
    con.close()
    return results


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return redirect("https://vodsearch.gg/")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
