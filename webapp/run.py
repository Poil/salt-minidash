import os
from flask import Flask, session, redirect, url_for, escape, request, jsonify
from pepper import Pepper, PepperException
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or 'UuX1Pieniuf1Ethu4ti9oeg2chahth4Y'


def check_auth():
    if all (k in session for k in ['username', 'password', 'eauth']):
        try:
            p = Pepper(api_url="http://salt.engsec:8000")
            p.login(username=session['username'], password=session['password'], eauth=session['eauth'])
            return p
        except PepperException:
            return False
    return False


@app.route('/')
def index():
    if check_auth():
        return ('<a href="/minions">minions</a>')
    return ("You are not logged in <br><a href = '/login'></b>"
            "click here to log in</b></a>")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
            session['username'] = request.form['username']
            session['password'] = request.form['password']
            session['eauth'] = request.form['eauth']
            return redirect(url_for('index'))
    return ('''<form action="" method="post">
                <p><input type="text" name="username" /></p>
                <p><input type="password" name="password" /></p>
                <p>
                  <select name="eauth">
                    <option value="pam">pam</option>
                  </select>
                </p>
                <p><input type="submit" value="Login" /></p>
            </form>''')


@app.route('/logout')
def logout():
    # remove the username from the session if it is there
    session.pop('username', None)
    session.pop('password', None)
    session.pop('auth_type', None)
    return redirect(url_for('index'))


@app.route('/minions', methods=['GET'])
def minion():
    """ minions """
    p = check_auth()
    minions_report = p.runner('manage.status')
    html = ('<table><thead><tr><th>Minion</th><th>Status</th>'
            '<th>OS</th><th>OS Release</th><th>Kernel</th></thead><tbody>')
    for status in minions_report.get('return', []):
        for state, minions in status.items():
            for minion in minions:
                grains = p.low({'fun': 'grains.items', 'tgt': minion, 'client': 'local'}).get(
                    'return', [])[0][minion]
                if not grains:
                    grains = {}
                html += (f'<tr><td><a href="/jobs/{minion}">{minion}</a></td><td>{state}</td>'
                         f"<td>{grains.get('osfullname')}</td><td>{grains.get('osrelease')}</td>"
                         f"<td>{grains.get('kernelrelease')}</td></tr>")
    html += '</tbody></table>'
    return html


@app.route('/jobs/<string:minion_id>', methods=['GET'])
def jobs(minion_id):
    p = check_auth()
    jobs_report = p.runner('jobs.list_jobs', search_target=minion_id)
    html = '<table><thead><tr><th>Job ID</th><th>Date</th><th>Type</th><th>Success</th></thead><tbody>'
    for jobsd in jobs_report.get('return', []):
        for job_id, job in jobsd.items():
            job_state = p.runner('jobs.exit_success', job_id)
            html += (f'<tr><td><a href="/job/{minion_id}/{job_id}">{job_id}</a></td>'
                     f"<td>{job['StartTime']}</td>"
                     f"<td>{job['Function']}</td>"
                     f"<td>{job_state}</td></tr>")
    html += '</tbody></table>'
    return html


@app.route('/job/<string:minion_id>/<string:job_id>', methods=['GET'])
def job(minion_id, job_id):
    p = check_auth()
    job_report = p.runner('jobs.lookup_jid', job_id)
    html = '<table><thead><tr><th>Resource</th><th>Result</th><th>Change</th></thead><tbody>'
    for jobd in job_report.get('return', []):
        for minion, report in jobd.items():
            if minion == minion_id:
                for resource, details in report.items():
                    html += (f"<tr><td>{resource}</td><td>{details['result']}</td>"
                             f"<td>{details.get('pchanges', '')}</td></tr>")
    html += '</tbody></table>'
    return html


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
