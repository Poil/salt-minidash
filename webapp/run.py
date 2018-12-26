import os
from flask import Flask, session, redirect, url_for, escape, request, jsonify, render_template
from pepper import Pepper, PepperException
import json
from datetime import datetime, timedelta
import itertools
import multiprocessing
from pprint import pprint

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
    return render_template('login.html.j2')


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
    my_minions = {}
    minions_l = (list(minions_report.get('return',[])[0].get('down')) +
                 list(minions_report.get('return',[])[0].get('up')))

    with multiprocessing.Pool(processes=20) as pool:
        results = pool.map(get_grains, minions_l)

    for status in minions_report.get('return', []):
        for state, minions in status.items():
            for minion_id in minions:
                grains = {}
                for res in results:
                    if res.get(minion_id):
                        grains = res[minion_id]
                        continue
                my_minions[minion_id] = { 'grains': grains, 'state': state }

    return render_template('minions.html.j2', my_minions=my_minions)


def get_grains(minion_id):
    p = check_auth()
    print('checking minion %s grains' % minion_id)
    #pprint(p.low({'fun': 'grains.items', 'tgt': minion_id, 'client': 'local'}))
    return p.local(fun='grains.items', tgt=minion_id.strip()).get('return')[0]

@app.route('/jobs/<string:minion_id>', methods=['GET'])
def jobs(minion_id):
    p = check_auth()
    yesterday = str(datetime.now() - timedelta(1))
    jobs_report = p.runner('jobs.list_jobs', search_target=minion_id, start_time=yesterday)
    my_jobs = {}

    for jobsd in jobs_report.get('return', []):
        jobs_id = jobsd.keys()
        with multiprocessing.Pool(processes=20) as pool:
            results = pool.starmap(job_exit, product([minion_id], jobs_id))

        for job_id, job in jobsd.items():
            my_jobs[job_id] = job
            my_jobs[job_id]['State'] = False
            for res in results:
                if res.get(minion_id):
                    my_jobs[job_id]['State'] = res[minion_id]
    return render_template('jobs.html.j2', minion_id=minion_id, my_jobs=my_jobs)


def job_exit(minion_id, job_id):
    p = check_auth()
    print('checking minion %s job_id %s' % (minion_id, job_id))
    return {minion_id: p.runner('jobs.exit_success', job_id).get('return',
        [{minion_id: False}])[0].get(minion_id, False)}


@app.route('/jobs/<string:minion_id>/<string:job_id>', methods=['GET'])
def job(minion_id, job_id):
    import json
    p = check_auth()
    job_report = p.runner('jobs.lookup_jid', job_id)
    my_job = {}

    for jobd in job_report.get('return', []):
        for type_report, report in jobd.items():
            if type(report) == dict:
                for minion, reportd in report.items():
                    if minion == minion_id:
                        for minion, details in report.items():
                            for resource, resource_detail in details.items():
                                rsc = resource.split('_|-')
                                my_job[resource] = {}
                                my_job[resource]['changes'] = json.dumps(
                                        resource_detail['changes'], indent=4, sort_keys=True)
                                my_job[resource]['type'] = rsc[0]
                                my_job[resource]['target'] = rsc[1]
                                my_job[resource]['apply'] = rsc[2]
                                my_job[resource]['option'] = rsc[3]
            else:
                print('%s is not a valid dict' % report)
    return render_template('job_details.html.j2', minion_id=minion_id, job_id=job_id, my_job=my_job)


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
