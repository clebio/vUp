# builtin
import logging
import json
from time import time

# shared
from library import db
from library import exc
from library import dockerhelper as docker

# config
from config import shared_config

# third party
from docker.errors import APIError

logger = logging.getLogger(shared_config.api_log_root_name + __name__)


# helpers
def proj_key(project_id):
    return "projects:project:{id}".format(id=project_id)


def proj_exists(project_id):
    project_key = proj_key(project_id)
    logger.debug("checking if proj key {p}".format(p=project_key))
    result = db.pipe.exists(name=project_key).execute()[0]
    logger.debug("retrieved result {r}".format(r=result))
    return True if result else None


# endpoint gate
def project_create(name, containers, version, project_id=None):
    new_project_id = project_id or str(int(time()))

    if proj_exists(new_project_id) and not project_id:
        new_project_id = str(int(time()) + 1)
    else:
        logger.debug("project {p} exists, updating".format(p=project_id))

    try:
        project = {"id": new_project_id, "name": name, "version": version, "containers": containers}
        db.pipe.set(name=proj_key(new_project_id), value=json.dumps(project)).execute()
        c = docker.get_client(host_url="tcp://docker1:2375")
        docker.create_containers_from_proj(docker_client=c, project_name=name, project_containers=containers)

    except APIError as e:
        if e.is_client_error():
            if "409" in str(e.response):
                raise exc.UserInvalidUsage("Project name '{n}' is already taken".format(n=name))
            else:
                raise exc.UserInvalidUsage("failed because {s}".format(s=e.explanation))

        else:
            raise exc.SystemInvalid("unable to create new project because {s}".format(s=e.explanation))

    except Exception as e:
        logger.error("failed to create new project because %s" % e, exc_info=True)
        # TODO rollback on error, deleting keys possibly created
        raise exc.SystemInvalid()

    return {"project_id": new_project_id, "created": True}


def project_listing(project_id=None):
    logger.debug("entered listing({args})".format(args=locals()))

    if project_id:
        if not proj_exists(project_id):
            raise exc.UserNotFound("no project with id {i}".format(id=project_id))
        else:
            results = db.pipe.get(name=proj_key(project_id)).execute()
            logger.debug("retrieved results {r}".format(r=results))
    else:
        try:  # pull all projects
            project_names = db.keys("projects:project:*") or []
            logger.debug("returning list of all projects: {p}".format(p=project_names))
            for project in project_names:
                db.pipe.get(name=project["name"])

            results = db.pipe.execute()
        except Exception as e:
            logger.error("failed to pull projects because %s" % e, exc_info=True)
            raise exc.SystemInvalid()

    projects = [json.loads(project) for project in results]
    logger.debug("returning project(s) {p}".format(p=projects))
    return projects



def project_delete(project_id):
    if proj_exists(project_id):
        db.pipe.delete(name=proj_key(project_id)).execute()
        return {"project_id": project_id, "state": "destroyed"}
    else:
        raise exc.UserNotFound("no project with id {p}".format(p=project_id))


def project_update(name, containers, version, project_id):
    project_delete(project_id=project_id)
    project_create(name=name, containers=containers, version=version)
    return {"project_id": project_id, "updated": True}







