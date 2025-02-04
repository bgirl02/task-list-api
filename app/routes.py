from flask import abort, Blueprint, jsonify, make_response, request
from app import db
from sqlalchemy import desc
from datetime import datetime
import os, requests
from dotenv import load_dotenv

from app.models.task import Task
from app.models.goal import Goal

# task
task_bp = Blueprint("tasks", __name__, url_prefix="/tasks")

@task_bp.route('', methods=['GET'])
def get_all_tasks():
    sort_query_value = request.args.get("sort") # has to be string
    if sort_query_value == 'asc':
        tasks = Task.query.order_by(Task.title).all()
    elif sort_query_value == 'desc':
        tasks = Task.query.order_by(desc(Task.title)).all()
    else:
        tasks = Task.query.all()

    result = []
    for item in tasks:
        result.append(item.to_dict())

    return jsonify(result), 200

@task_bp.route('/<task_id>', methods=['GET'])
def get_one_task(task_id):
    chosen_task = get_model_from_id(Task, task_id)
    return jsonify({"task": chosen_task.to_dict()}), 200

@task_bp.route('', methods=['POST'])
def create_one_task():
    request_body = request.get_json()

    try:
        new_task = Task.from_dict(request_body)
    except KeyError:
        return jsonify({"details": "Invalid data"}), 400

    db.session.add(new_task)
    db.session.commit()

    return jsonify({"task": new_task.to_dict()}), 201

@task_bp.route('/<task_id>', methods=['PUT'])
def update_one_task(task_id):
    update_task = get_model_from_id(Task, task_id)

    request_body = request.get_json()

    try:
        update_task.title = request_body["title"]
        update_task.description = request_body["description"]
    except KeyError:
        return jsonify({"msg": "Missing needed data"}), 400 

    db.session.commit()
    return jsonify({"task": update_task.to_dict()}), 200

@task_bp.route('/<task_id>', methods=['DELETE'])
def delete_one_task(task_id):
    task_to_delete = get_model_from_id(Task, task_id)

    db.session.delete(task_to_delete)
    db.session.commit()

    return jsonify({"details": f'Task {task_to_delete.task_id} "{task_to_delete.title}" successfully deleted'}), 200

@task_bp.route('/<task_id>/<mark_tf>', methods=['PATCH'])
def change_value_of_task(task_id, mark_tf):
    task_to_patch = get_model_from_id(Task, task_id)

    try:
        if mark_tf == 'mark_complete':
            task_to_patch.is_complete = True # True or False
            task_to_patch.completed_at = datetime.utcnow()
            slackbot(task_to_patch.title)
        elif mark_tf == 'mark_incomplete':
            task_to_patch.is_complete = False # True or False
            task_to_patch.completed_at = None
    except KeyError:
        return jsonify({"msg": "Missing needed data"}), 400 

    db.session.commit()
    return jsonify({"task": task_to_patch.to_dict()}), 200


# goal
goal_bp = Blueprint("goals", __name__, url_prefix="/goals")

@goal_bp.route('', methods=['GET'])
def get_all_goals():
    goals = Goal.query.all()

    result = []
    for item in goals:
        result.append(item.to_dict())

    return jsonify(result), 200

@goal_bp.route('/<goal_id>', methods=['GET'])
def get_one_goal(goal_id):
    chosen_goal = get_model_from_id(Goal, goal_id)
    return jsonify({"goal": chosen_goal.to_dict()}), 200

@goal_bp.route('', methods=['POST'])
def create_one_goal():
    request_body = request.get_json()

    try:
        new_goal = Goal.from_dict(request_body)
    except KeyError:
        return jsonify({"details": "Invalid data"}), 400

    db.session.add(new_goal)
    db.session.commit()

    return jsonify({"goal": new_goal.to_dict()}), 201

@goal_bp.route('/<goal_id>', methods=['PUT'])
def update_one_goal(goal_id):
    update_goal = get_model_from_id(Goal, goal_id)

    request_body = request.get_json()

    try:
        update_goal.title = request_body["title"]
    except KeyError:
        return jsonify({"msg": "Missing needed data"}), 400 

    db.session.commit()
    return jsonify({"goal": update_goal.to_dict()}), 200

@goal_bp.route('/<goal_id>', methods=['DELETE'])
def delete_one_goal(goal_id):
    goal_to_delete = get_model_from_id(Goal, goal_id)

    db.session.delete(goal_to_delete)
    db.session.commit()

    return jsonify({"details": f'Goal {goal_to_delete.goal_id} "{goal_to_delete.title}" successfully deleted'}), 200

@goal_bp.route('/<goal_id>/tasks', methods=['GET'])
def get_tasks_for_goal(goal_id):
    chosen_goal = get_model_from_id(Goal, goal_id)

    return jsonify(chosen_goal.to_dict_task()), 200

@goal_bp.route('/<goal_id>/tasks', methods=['POST'])
def create_tasks_for_goal(goal_id):
    matching_goal = Goal.query.get(goal_id)

    request_body = request.get_json()
    task_ids = request_body["task_ids"]
    
    tasks = matching_goal.get_task_list()
    goal_task_ids = [x["id"] for x in tasks]
    for tid in task_ids: 
        if tid not in goal_task_ids:
            new_task = Task(
                title="",
                description="",
                is_complete=False,
                goal_id = matching_goal.goal_id
            )
            db.session.add(new_task)
            db.session.commit()

    response_dict = {"id": matching_goal.goal_id,
                    "task_ids": task_ids}

    return jsonify(response_dict), 200


def get_model_from_id(cls, model_id):
    try:
        model_id = int(model_id)
    except ValueError:
        return abort(make_response({"msg": f"invalid data: {model_id}"}, 400))

    chosen_model = cls.query.get(model_id)

    if chosen_model is None:
        return abort(make_response({"msg": f"Could not find item with id: {model_id}"}, 404))

    return chosen_model

def slackbot(text):
    slack_auth=os.environ.get("SLACK_AUTH")
    path = "https://slack.com/api/chat.postMessage"

    query_params = {
        "channel": "task-notifications",
        "text": f"Someone just completed the task {text}"
    }

    query_headers = {"Authorization": slack_auth}

    response = requests.get(path, params=query_params, headers=query_headers)
