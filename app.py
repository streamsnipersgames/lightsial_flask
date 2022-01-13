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


def get_token(db_connection, client_name):
    with db_connection.cursor() as cur:
        cur.execute(f"select token from api_tokens where clientname = '{client_name}'")
        token = cur.fetchall()
    assert len(token) == 1
    return token[0][0]


@app.route('/api/gsk/fifa_add_fixture', methods=('GET', 'POST'))
def post_gsk_fifa_new_fixture():
    con = establish_db_connection()
    token = get_token(con, "gsk")
    if request.method == 'POST':
        # get parameter from the form
        if "Authorization" not in request.headers:
            return "missing token", 401
        if token != request.headers["Authorization"]:
            return "bad or expired token, please contact rob@vodsearch.tv to fix", 401
        twitch_url = request.form.get('twitch_url', None)
        if twitch_url is None:
            return "must supply twitch_url", 400
        fixture_id = request.form.get('fixture_id', None)
        with con.cursor() as cur:
            # to avoid sql injections parametrised/compiled query
            cur.execute(
                "INSERT INTO api_gsk_fifa (twitch_url, fixture_id, added_on_to_db) VALUES (%s, %s, %s)",
                (twitch_url, fixture_id, int(datetime.now().timestamp())),
            )
            con.commit()
        con.close()
        return "success", 201
    # return render_template('twitch_url.html', status=status)
    return "error", 400


@app.route('/api/duel/supported_games/', methods=('GET',))
def get_duel_supported_games():
    con = establish_db_connection()
    token = get_token(con, "duel")
    status = None
    if request.method == "GET":
        if "Authorization" not in request.headers:
            return "missing token", 401
        if token != request.headers["Authorization"]:
            return "bad or expired token, please contact rob@vodsearch.tv to fix", 401
        with con.cursor() as cur:
            cur.execute("select game_id, game_name from api_duel_supportedgames")
            results = json.dumps({x[0]: x[1] for x in cur.fetchall()})
    else:
        results = json.dumps({})
    con.close()
    return results


def get_duel_game_ids(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("select game_id from api_duel_supportedgames")
        results = cur.fetchall()
    return [x[0] for x in results]


@app.route('/api/duel/add_new_booking/', methods=('POST',))
def post_duel_booking():
    con = establish_db_connection()
    token = get_token(con, "duel")
    status = None
    required_fields = ("booking_id", "starts_at", "ends_at", "igdb_game_id", "igdb_platform_id", "vod_url")
    if request.method == "POST":
        if "Authorization" not in request.headers:
            return "missing token", 401
        if token != request.headers["Authorization"]:
            return "bad or expired token, please contact rob@vodsearch.tv to fix", 401
        if set(request.form.keys()) != set(required_fields):
            return f"info provided doesn't match expectation, expecting fields: {required_fields}", 400
        ts_start, ts_end, ts_now = int(request.form["starts_at"]), int(request.form["ends_at"]), int(datetime.now().timestamp())
        if ts_start > ts_end:
            return "starting timestamp is after ending timestamp, please check your info", 400
        if ts_start < ts_now:
            return "starting timestamp is in the past, too late to watch this event", 400
        if ts_start - ts_now > 365 * 60 * 60:
            return "starting timestamp > 1yr from today, please double-check", 400
        if ts_end - ts_start > 3 * 60 * 60:
            return "duel is longer than 3 hours, please double-check your start and end times", 400
        if ts_end - ts_start < 60:
            return "duel is shorter than 1 minute, please double-check your start and end times", 400
        supported_game_ids = get_duel_game_ids(con)
        if int(request.form["igdb_game_id"]) not in supported_game_ids:
            return f"game not supported, currently supported games are: {supported_game_ids}", 400
        try:
            with con.cursor() as cur:
                cur.execute(
                    f"insert into api_duel_bookings ({', '.join(required_fields)}) values (%s, %s, %s, %s, %s, %s)",
                    tuple([request.form[field] for field in required_fields]),
                )
            con.commit()
            con.close()
            return "Success.", 201
        except:
            return "unexpected error", 400


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return redirect("https://vodsearch.gg/")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
