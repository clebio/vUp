from docker import Client


def get_client(host_url):
    """ Returns a docker api client """
    c = Client(base_url=host_url)
    # TODO: Test connection
    return c


def create_container(docker_client, image_name, container_name, env=None, links=None, ports=None, volumes=None, volumes_from=None, command=None):
    #  Links can be specified with the links argument. They can either be specified as a dictionary mapping name to alias or as a list of (name, alias) tuples.
    container = docker_client.create_container(image=image_name, environment=env, name=container_name, command=command)
    if volumes is not None:
        vol_binding = {}
        for vol in volumes:
            vol_binding[volumes[vol]] = {
                        'bind': vol,
                        'ro': False
                    }
    else:
        vol_binding = None
    response = docker_client.start(container=container.get('Id'), links=links, binds=vol_binding, volumes_from=volumes_from)
    # Return the container id
    return container.get('Id')
    

def create_mysql(docker_client, container_name, db_name, db_user, db_pass=None, db_sql=None):
    env = {
                "MYSQL_USER": db_user,
                "MYSQL_PASS": db_pass if db_pass is not None else "**Random**",
            }
    return create_container(docker_client, "mysql:latest", container_name, env)

def create_nginx(docker_client, container_name):
    # Links can be specified with the links argument. They can either be specified as a dictionary mapping name to alias or as a list of (name, alias) tuples.
    return create_container(docker_client=docker_client, image_name="debian", container_name=container_name, env=None, links=[('mysql1', 'mysql')])

def create_storage(docker_client, container_name, storage_url):
    if 'local://' in storage_url:
        # Only local storage is supported right now.   Path has to exist on the docker host machine
        local_path = storage_url.replace('local://', '')
        return create_container(docker_client=docker_client, container_name=container_name, image_name="debian", volumes={'/data': local_path}, command="/bin/bash -c 'while /bin/true; do sleep 300;done'")
    else:
        raise RuntimeError("%s not supported.  Use local://" % storage_url)

def create_phpfpm(docker_client, container_name, storage_container, db_container):
    return create_container(docker_client=docker_client, image_name="php-fpm", container_name=container_name, volumes_from=[storage_container], links=[(db_container, 'db')]) 

def get_ip(docker_client, container_id):
    return docker_client.inspect_container(container=container_id)['NetworkSettings']['IPAddress']

def create_containers_from_proj(docker_client, project_name, project_containers):
    prefix = project_name.strip().replace(' ').lower() + "_"
    # TODO: Get a list of existing containers for project
    # TODO: Error handling
    for container in project_containers:
        clean_name = container['name'].strip().replace(' ').lower()
        container_name = "%s%s" % (prefix, clean_name) 

        if 'link' in container:
            links = []
            for link in container['link']:
                links.append(("%s%s" % (prefix, link.strip().replace(" ").lower())), link)
        else:
            links = None

        if container['type'] == "storage":
            return create_storage(docker_client=docker_client, container_name=container_name, storage_url=container['data_source'])
        elif container['type'] == "nginx":
            return create_nginx(docker_client=docker_client, container_name=container_name, links=links)
        elif container['type'] == "mysql":
            return create_mysql(docker_client=docker_client, container_name=container_name, db_name=container['mysql_name'], db_user=container['mysql_user'], db_pass=container['mysql_pass'], db_sql=container['mysql_sql'])
        elif container['type'] == "php":
            return create_phpfpm(docker_client=docker_client, container_name=container_name, volumes_from=[container['volumes_from']], links=links)
