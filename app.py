from flask import Flask, redirect, render_template, request
from flask_cors import cross_origin
import psycopg2, json, string
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


@app.route('/api/gsk/fifa/', methods=('POST', 'GET', 'DELETE'), strict_slashes=False)
@cross_origin()
def post_gsk_fifa_new_fixture():
    con = establish_db_connection()
    token = get_token(con, "gsk")
    if "authorization" not in request.headers:
        con.close()
        return "missing token", 401
    if token != request.headers["authorization"]:
        con.close()
        return "bad or expired token, please contact rob@vodsearch.tv to fix", 401
    if request.method == 'POST':
        twitch_url = request.form.get('twitch_url', None)
        fixture_id = request.form.get('fixture_id', None)
        ts_start = request.form.get("ts_start", int(datetime.now().timestamp()))
        early_stop = request.form.get("early_stop", None)

        if fixture_id is None:
            con.close()
            return "must supply fixture_id", 400
        with con.cursor() as cur:
            cur.execute(f"select count(id) from api_gsk_fifa where fixture_id = {fixture_id}")
            results = cur.fetchall()
        n_data_with_fixture = results[0][0]
        if early_stop is None:
            # unless this is an early stop, make sure fixture id doesn't already exist
            if n_data_with_fixture > 0:
                con.close()
                return f"fixture_id {fixture_id} already exists, please choose a new one", 400
        else:
            # if this is an early stop, stop it
            if n_data_with_fixture > 0:
                with con.cursor() as cur:
                    cur.execute(
                        "UPDATE api_gsk_fifa set status = 2 where fixture_id = %s", (fixture_id, ),
                    )
                con.commit()
                con.close()
                return "success", 201
            else:
                con.close()
                return f"fixture_id {fixture_id} not found in database", 400

        if twitch_url is None:
            con.close()
            return "must supply twitch_url (url to watch)", 400

        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO api_gsk_fifa (twitch_url, fixture_id, ts_start, added_on_to_db, status) VALUES (%s, %s, %s, %s, 0)",
                (twitch_url, fixture_id, int(ts_start), int(datetime.now().timestamp())),
            )
            con.commit()
            con.close()
            return "success", 201
    if request.method == 'DELETE':
        fixture_id = request.form.get('fixture_id', None)
        if fixture_id is None:
            con.close()
            return "must supply fixture_id", 400
        with con.cursor() as cur:
            cur.execute(f"select count(id) from api_gsk_fifa where fixture_id = {fixture_id}")
            results = cur.fetchall()
        if results[0][0] == 0:
            con.close()
            return f"fixture_id {fixture_id} is not in our database, so we can't remove it", 400
        else:
            with con.cursor() as cur:
                cur.execute(f"delete from api_gsk_fifa where fixture_id = {fixture_id}")
            con.commit()
            con.close()
            return "success", 201
    if request.method == "GET":
        with con.cursor() as cur:
            cur.execute(f"select fixture_id from api_gsk_fifa")
            results = cur.fetchall()
            con.close()
            fixture_ids = [str(x[0]) for x in results]
            return f"fixture ids in our database: {', '.join(fixture_ids)}"


def get_duel_game_ids(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("select game_id, platform_id from api_duel_supportedgames where game_ready")
        results = cur.fetchall()
    return [{"igdb_game_slug": x[0], "igdb_platform_id": x[1]} for x in results]


def get_wehype_stfc_creators(db_connection, table_name):
    with db_connection.cursor() as cur:
        cur.execute(f"select creator from {table_name}")
        results = cur.fetchall()
    return [x[0] for x in results]


@app.route('/api/duel/booking/', methods=('GET', 'POST', 'DELETE', 'PUT', 'PATCH', ), strict_slashes=False)
def post_duel_booking():
    # url_test = "https://filesamples.com/samples/video/flv/sample_640x360.flv"
    url_test = "https://streamsnipers.s3.us-east-2.amazonaws.com/samples/sample.mp4"
    safe_chars = string.ascii_lowercase + string.ascii_uppercase + string.digits + '.-_'
    con = establish_db_connection()
    token = get_token(con, "duel")
    status = None
    if "Authorization" not in request.headers:
        con.close()
        return {"success": False, "description": "missing token"}, 401
    if token != request.headers["Authorization"]:
        con.close()
        return {"success": False, "description": "bad or expired token, please contact rob@vodsearch.tv to fix"}, 401
    if request.method == "GET":
        # return supported games
        results = get_duel_game_ids(con)
        con.close()
        return {"success": True, "description": "", "games": results}, 200
    elif request.method == "DELETE":
        # delete existing booking
        if set(request.form.keys()) != {"booking_id"}:
            con.close()
            return {"success": False, "description": "only field provided must be 'booking_id'"}, 400
        with con.cursor() as cur:
            cur.execute("select id from api_duel_bookings where booking_id = %s", (request.form["booking_id"], ))
            results = cur.fetchall()
        if len(results) == 0:
            con.close()
            return {"success": False, "description": "booking_id provided not found"}, 422
        with con.cursor() as cur:
            cur.execute("delete from api_duel_bookings where booking_id = %s", (request.form["booking_id"], ))
        con.commit()
        con.close()
        return {"success": True, "description": ""}, 200
    elif request.method in ["POST", "PUT", "PATCH"]:
        # add new booking or modify existing booking
        required_fields = ("booking_id", "starts_at", "ends_at", "igdb_game_slug", "igdb_platform_id", "vod_url")
        error_msg = None
        request_form = dict(request.form)
        test_all = bool(request_form.pop("test_all", False))
        test_highlights = bool(request_form.pop("test_highlights", False))
        # check for errors
        ts_now = datetime.now().timestamp()
        if set(request_form.keys()) != set(required_fields):
            # fields don't match
            error_msg = f"info provided doesn't match expectation, expecting fields: {required_fields}"
        else:
            # fields match, so check other stuff
            if test_all:
                request_form["starts_at"] = ts_now + 20
                request_form["ends_at"] = ts_now + 80
                request_form["vod_url"] = url_test
            if test_all or test_highlights:
                request_form["igdb_game_slug"] = "fortnite"
                request_form["igdb_platform_id"] = 6
            ts_start, ts_end = int(request_form["starts_at"]), int(request_form["ends_at"])
            if ts_start > ts_end:
                error_msg = "starting timestamp is after ending timestamp, please check your info"
            elif ts_start < ts_now:
                error_msg = "starting timestamp is in the past, too late to watch this event"
            elif ts_start - ts_now > 365 * 60 * 60:
                error_msg = "starting timestamp > 1yr from today, please double-check"
            elif ts_end - ts_start > 3 * 60 * 60:
                error_msg = "duel is longer than 3 hours, please double-check your start and end times"
            elif (ts_end - ts_start < 60) and not test_all:
                error_msg = "duel is shorter than 1 minute, please double-check your start and end times"
        if error_msg is not None:
            con.close()
            return {"success": False, "description": error_msg}, 422
        supported_games_and_platforms = [(x["igdb_game_slug"], x["igdb_platform_id"]) for x in get_duel_game_ids(con)]
        game_id, platform_id = request_form["igdb_game_slug"], int(request_form["igdb_platform_id"])
        for c in game_id:
            if c not in safe_chars:
                return {"success": True, "description": f"bad character in igdb_game_slug, accepts only: {safe_chars}"}, 400
        if (game_id, platform_id) not in supported_games_and_platforms:
            con.close()
            return {"success": False, "description": f"(game, platform) pair not supported, currently supporting: {supported_games_and_platforms}"}, 422
        if request.method == "POST":
            # first, just confirm the booking id doesn't already exist in our system
            with con.cursor() as cur:
                cur.execute(f"select id from api_duel_bookings where booking_id = %s", (request_form["booking_id"], ))
                result = cur.fetchall()
            if len(result) > 0:
                con.close()
                return {"success": False, "description": "this booking id already exists, did you mean to send a PUT/PATCH request instead?"}, 422
            with con.cursor() as cur:
                cur.execute(
                    f"insert into api_duel_bookings ({', '.join(required_fields)}) values (%s, %s, %s, %s, %s, %s)",
                    tuple([request_form[field] for field in required_fields]),
                )
            con.commit()
            con.close()
            return {"success": True, "description": ""}, 201
        elif request.method in ["PUT", "PATCH"]:
            booking_id = request.form["booking_id"]
            with con.cursor() as cur:
                cur.execute(f"select id from api_duel_bookings where booking_id = %s", (booking_id, ))
                result = cur.fetchall()
                if len(result) == 0:
                    con.close()
                    return {"success": False, "description": "booking id not recognized"}, 422
                booking_id = result[0][0]
                field_cmd = ", ".join([f"{field} = %s" for field in required_fields])
                field_values = [request.form.get(field) for field in required_fields]
                cur.execute(
                    f"update api_duel_bookings set {field_cmd} where id = {booking_id}", tuple(field_values),
                )
            con.commit()
            con.close()
            return {"success": True, "description": ""}, 201


@app.route('/api/wehype/stfc/', methods=('GET', 'POST', 'DELETE', ), strict_slashes=False)
def api_wehype_stfc():
    con = establish_db_connection()
    token = get_token(con, "wehype")
    table_name = "api_wehype_stfc"
    status = None
    if "Authorization" not in request.headers:
        con.close()
        return {"success": False, "description": "missing token"}, 401
    if token != request.headers["Authorization"]:
        con.close()
        return {"success": False, "description": "bad or expired token, please contact rob@vodsearch.tv to fix"}, 401
    if request.method == "GET":
        # return supported games
        results = get_wehype_stfc_creators(con, table_name)
        con.close()
        return {"success": True, "description": "", "creators": results}, 200
    elif request.method == "DELETE":
        # delete existing creator
        if set(request.form.keys()) != {"creator"}:
            con.close()
            return {"success": False, "description": "only field provided must be 'creator'"}, 400
        with con.cursor() as cur:
            cur.execute(f"select id from {table_name} where creator = %s", (request.form["creator"], ))
            results = cur.fetchall()
        if len(results) == 0:
            con.close()
            return {"success": False, "description": "creator provided not found"}, 400
        with con.cursor() as cur:
            cur.execute(f"delete from {table_name} where creator = %s", (request.form["creator"], ))
        con.commit()
        con.close()
        return {"success": True, "description": ""}, 201
    elif request.method == "POST":
        # import ipdb; ipdb.set_trace()
        # add new creator or modify existing creator
        required_fields = ("creator", )
        error_msg = None
        if set(request.form.keys()) != set(required_fields):
            # fields don't match
            error_msg = f"info provided doesn't match expectation, expecting fields: {required_fields}"
        if error_msg is not None:
            con.close()
            return {"success": False, "description": error_msg}, 400
        # first, just confirm the creator doesn't already exist in our system
        with con.cursor() as cur:
            cur.execute(f"select id from {table_name} where creator = %s", (request.form["creator"], ))
            result = cur.fetchall()
        if len(result) > 0:
            con.close()
            return {"success": False, "description": "this creator has already been entered, did you mean to send another?"}, 400
        with con.cursor() as cur:
            cur.execute(
                f"insert into {table_name} ({', '.join(required_fields)}) values (%s)",
                tuple([request.form[field] for field in required_fields]),
            )
        con.commit()
        con.close()
        return {"success": True, "description": ""}, 201


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return redirect("https://vodsearch.gg/")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
