#!/usr/bin/env python3

import argparse
import os
import time
import yaml
import json
import sys
from importlib import import_module

import pycloudmessenger.ffl.abstractions as ffl
import pycloudmessenger.ffl.fflapi as fflapi


fl_path = os.path.abspath('.')
if fl_path not in sys.path:
    sys.path.append(fl_path)

from examples.constants import GENERATE_CONFIG_DESC, NUM_PARTIES_DESC, \
    PATH_CONFIG_DESC, CONF_PATH, MODEL_CONFIG_DESC, NEW_DESC, NAME_DESC, \
    FL_EXAMPLES, FL_CONN_TYPES, CONNECTION_TYPE_DESC, FL_MODELS, \
    FUSION_CONFIG_DESC, TASK_NAME_DESC, EXAMPLES_WARNING


def check_valid_folder_structure(p):
    """
    Checks that the folder structure is valid

    :param p: an argument parser
    :type p: argparse.ArgumentParser
    """
    for folder in FL_EXAMPLES:
        if not os.path.isfile(os.path.join("examples", folder, "README.md")) and not os.path.isfile(os.path.join(
                "examples", folder, "generate_configs.py")):
            p.error(
                "Bad folder structure: '{}' directory is missing files.".format(folder))


def setup_parser():
    """
    Sets up the parser for Python script

    :return: a command line parser
    :rtype: argparse.ArgumentParser
    """
    p = argparse.ArgumentParser(description=GENERATE_CONFIG_DESC)
    p.add_argument("--num_parties", "-n", help=NUM_PARTIES_DESC,
                   type=int, required=True)
    p.add_argument("--dataset", "-d",
                   help="Dataset code from examples", type=str, required=True)

    p.add_argument("--data_path", "-p", help=PATH_CONFIG_DESC, required=True)
    p.add_argument("--config_path", "-conf_path", help=CONF_PATH)
    p.add_argument("--model", "-m", help=MODEL_CONFIG_DESC, choices=[os.path.basename(
        d) for d in FL_MODELS], required=False, default=None)
    p.add_argument("--fusion", "-f", help=FUSION_CONFIG_DESC ,required=False, choices=[os.path.basename(
        d) for d in FL_EXAMPLES])
    p.add_argument("--create_new", "-new", action="store_true", help=NEW_DESC)
    p.add_argument("--name", help=NAME_DESC)
    p.add_argument("--connection", "-c", choices=[os.path.basename(
        d) for d in FL_CONN_TYPES], help=CONNECTION_TYPE_DESC, required=False, default="flask")
    p.add_argument("--task_name", "-t", help=TASK_NAME_DESC, required=False)
    return p


def rabbit_task(credentials: str, aggregator: str, password: str, task_name: str):
    try:
        ffl.Factory.register(
            'cloud',
            fflapi.Context,
            fflapi.User,
            fflapi.Aggregator,
            fflapi.Participant
        )

        context = ffl.Factory.context(
            'cloud',
            credentials,
            aggregator,
            password
        )

        user = ffl.Factory.user(context)

        with user:
            result = user.create_task(task_name, ffl.Topology.star, {})
            print(f"Task '{task_name}' created.")
    except Exception as err:
        print('error: %s', err)
        raise

def generate_connection_config(conn_type, party_id=0, is_party=False, task_name = None):
    connection = {}

    if conn_type == 'flask':
        tls_config = {
            'enable': False
        }
        connection = {
            'name': 'FlaskConnection',
            'path': 'ibmfl.connection.flask_connection',
            'sync': False
        }
        if is_party:
            connection['info'] = {
                'ip': '127.0.0.1',
                'port': 8085 + party_id
            }
        else:
            connection['info'] = {
                'ip': '127.0.0.1',
                'port': 5000
            }
        connection['info']['tls_config'] = tls_config
    if conn_type == 'rabbitmq':
        credentials = os.environ.get('IBMFL_BROKER')
        if not credentials:
            raise Exception("IBMFL_BROKER: environment variable not available.")

        credentials = yaml.load(credentials)
        if 'rabbit' in credentials:
            key = 'rabbit'
        elif 'connection' in credentials:
            key = 'connection'
        else:
            raise Exception("IBMFL_BROKER: environment variable not formatted correctly.")

        with open('ibmfl_broker_connection.json', 'w') as creds:
            creds.write(json.dumps(credentials[key]))

        connection = {
            'name': 'RabbitMQConnection',
            'path': 'ibmfl.connection.rabbitmq_connection',
            'sync': True
        }
        if is_party:
            party = credentials[f'party{party_id}']['name']
            password = credentials[f'party{party_id}']['password']
            connection['info'] = {
                'credentials': 'ibmfl_broker_connection.json',
                'user': party,
                'password': password,
                'role': 'party',
                'task_name': task_name
            }

        else:
            aggregator = credentials['aggregator']['name']
            password = credentials['aggregator']['password']
            connection['info'] = {
                'credentials': 'ibmfl_broker_connection.json',
                'user': aggregator,
                'password': password,
                'role': 'aggregator',
                'task_name': task_name
            }

            rabbit_task('ibmfl_broker_connection.json', aggregator, password, task_name)

    return connection


def get_aggregator_info(conn_type):

    if conn_type == 'flask':
        aggregator = {
            'ip': '127.0.0.1',
            'port': 5000
        }
    else:
        aggregator = {}

    return aggregator


def get_privacy():
    privacy = {
        'metrics': True
    }

    return privacy


def generate_ph_config(module, conn_type, is_party=False, party_id=None):
    if is_party:
        protocol_handler = {
            'name': 'PartyProtocolHandler',
            'path': 'ibmfl.party.party_protocol_handler'
        }
    else:
        protocol_handler = {
            'name': 'ProtoHandler',
            'path': 'ibmfl.aggregator.protohandler.proto_handler'
        }
    if conn_type == 'rabbitmq':
        protocol_handler['name'] += 'RabbitMQ'


    return protocol_handler


def generate_fusion_config(module):
    gen_fusion_config = getattr(module, 'get_fusion_config')
    return gen_fusion_config()


def generate_hp_config(model, module, num_parties):
    gen_hp_config = getattr(module, 'get_hyperparams')
    hp = gen_hp_config(model)
    hp['global']['num_parties'] = num_parties

    return hp


def generate_model_config(module, model, folder_configs, dataset, is_agg=False, party_id=0):
    get_model_config = getattr(module, 'get_model_config')
    model = get_model_config(folder_configs, dataset, is_agg, party_id, model=model)

    return model


def generate_lt_config(module):
    get_local_training_config = getattr(module, 'get_local_training_config')
    return get_local_training_config()


def generate_datahandler_config(module, model, party_id, dataset, folder_data, is_agg=False):

    get_data_handler_config = getattr(module, 'get_data_handler_config')
    dh = get_data_handler_config(party_id, dataset, folder_data, is_agg, model=model)

    return dh


def generate_agg_config(module, model, num_parties, conn_type, 
                                    dataset, folder_data, folder_configs, task_name = None):

    if not os.path.exists(folder_configs):
        os.makedirs(folder_configs)
    config_file = os.path.join(folder_configs, 'config_agg.yml')

    content = {
        'connection': generate_connection_config(conn_type, task_name=task_name),
        'fusion': generate_fusion_config(module),
        'hyperparams': generate_hp_config(model, module, num_parties),
    }

    content['protocol_handler'] = generate_ph_config(module, conn_type, is_party=False)

    model_config = generate_model_config(module, model, folder_configs, dataset, True)
    data = generate_datahandler_config(module, model, 0, dataset, folder_data, True)
    if model_config:
        content['model'] = model_config
    if data:
        content['data'] = data

    with open(config_file, 'w') as outfile:
        yaml.dump(content, outfile)

    print('Finished generating config file for aggregator. Files can be found in: ',
          os.path.abspath(os.path.join(folder_configs, 'config_agg.yml')))


def generate_party_config(module, model, num_parties, conn_type, 
                                    dataset, folder_data, folder_configs, task_name = None):

    for i in range(num_parties):
        config_file = os.path.join(
            folder_configs, 'config_party' + str(i) + '.yml')

        ph = generate_ph_config(module, conn_type, is_party=True)

        content = {
            'connection': generate_connection_config(conn_type, i, True, task_name=task_name),
            'data': generate_datahandler_config(module, model, i, dataset, folder_data),
            'model': generate_model_config(module, model, folder_configs, dataset, party_id=i),
            'protocol_handler': ph,
            'local_training': generate_lt_config(module),
            'aggregator': get_aggregator_info(conn_type),
            'privacy': get_privacy()
        }

        with open(config_file, 'w') as outfile:
            yaml.dump(content, outfile)

    print('Finished generating config file for parties. Files can be found in: ',
          os.path.abspath(os.path.join(folder_configs, 'config_party*.yml')))



if __name__ == '__main__':
    # Parse command line options
    parser = setup_parser()
    args = parser.parse_args()
    #check_valid_folder_structure(parser)

    # Collect arguments
    num_parties = args.num_parties
    dataset = args.dataset
    party_data_path = args.data_path
    config_path = args.config_path
    model = args.model
    fusion = args.fusion
    create_new = args.create_new
    exp_name = args.name
    conn_type = args.connection
    task_name = args.task_name

    # Create folder to save configs
    if config_path:
        if not os.path.exists(config_path):
            print('Config Path:{} does not exist.'.format(config_path))
            print('Creating {}'.format(config_path))
            try:
                os.makedirs(config_path, exist_ok=True)
            except OSError:
                print('Creating directory {} failed'.format(config_path))
                sys.exit(1)
        folder_configs = os.path.join(config_path, "configs")
    else:
        folder_configs = os.path.join("examples", "configs")
    if not model or model == "None" or model == "default":
        model = ''
        
    if create_new:
        folder_configs = os.path.join(
            folder_configs, exp_name if exp_name else str(int(time.time())))
    elif model == 'keras_classifier':
        folder_configs = os.path.join(folder_configs, model)        
    else:
        folder_configs = os.path.join(folder_configs, fusion, model)

    # To support tutorials which still have examples with old format
    if(model == 'keras_classifier'):
        model = 'keras'
        fusion = 'iter_avg'
        print(EXAMPLES_WARNING)
    # Import and run generate_configs.py
    config_fusion = import_module('examples.{}.generate_configs'.format(fusion))
 
 

    generate_agg_config(config_fusion, model, num_parties, conn_type, 
                            dataset, party_data_path, folder_configs, task_name)
    generate_party_config(config_fusion, model, num_parties, conn_type, 
                            dataset, party_data_path, folder_configs, task_name)
