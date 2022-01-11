from flask import Flask, redirect, render_template, request
import psycopg2
import datetime
from decouple import config
print(config)
# not preferred method to use pycog directly. good enough for first step
# preferred method is SQLAlchemy
con = psycopg2.connect(
    user=config('DB_USER'),
    password=config('PASSWORD'),
    host=config('HOST'),
    database=config('DB_NAME'),
    port=config('PORT')
)

app = Flask(__name__)


@app.route('/api/url-reader/gamescorekeeper/', methods=('GET', 'POST'))
def gameScoreKeeper():
    status = None
    if request.method == 'POST':
        # get parameter from the form
        twitch_url = request.form['twitch_url']
        # get cursor
        cur = con.cursor()
        # to avoid sql injections parametrised/compiled query
        cur.execute("INSERT INTO common_site_valorant_twitch_url (twitch_url, added_on_to_db) VALUES (%s, %s)", (twitch_url, datetime.datetime.now()))
        # commit transactions
        con.commit()
        # close curson and connection
        cur.close()
        cur.close()

        # TODO: add error check
        status = True
        return render_template('twitch_url.html', status=status)
    else:
        return render_template('twitch_url.html', status=status)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return redirect("https://vodsearch.gg/")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
