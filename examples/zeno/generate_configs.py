import os
import numpy as np
from importlib import import_module

import examples.datahandlers as datahandlers


def get_fusion_config():
    fusion = {
        'name': 'ZenoGradientFusionHandler',
        'path': 'ibmfl.aggregator.fusion.zeno_gradient_fusion_handler'
    }
    return fusion


def get_local_training_config():
    local_training_handler = {
        'name': 'GradientLocalTrainingHandler',
        'path': 'ibmfl.party.training.gradient_local_training_handler'
    }
    return local_training_handler


def get_hyperparams(model):
    hyperparams = {
        'global': {
                'rounds': 3,
                'termination_accuracy': 0.9,
                'max_timeout': 60
            }
    }
    current_module = globals().get('__package__')
    
    model_module = import_module('{}.model_{}'.format(current_module, model))
    local_params_method = getattr(model_module, 'get_hyperparams')

    local_params = local_params_method()
    hyperparams['local'] = local_params
    
    return hyperparams


def get_data_handler_config(party_id, dataset, folder_data, is_agg=False, model='keras'):

    SUPPORTED_DATASETS = ['mnist']
    if dataset in SUPPORTED_DATASETS:
        if dataset == 'mnist' and model == 'tf':
            dataset = 'mnist_tf'

        if dataset == 'mnist' and model == 'pytorch':
            dataset = 'mnist_pytorch'

        data = datahandlers.get_datahandler_config(
            dataset, folder_data, party_id, is_agg)
    else:
        raise Exception(
            "The dataset {} is a wrong combination for fusion/model".format(dataset))
    return data


def get_model_config(folder_configs, dataset, is_agg=False, party_id=0,
                     model='keras'):
    SUPPORTED_MODELS = ['keras', 'pytorch', 'tf']

    if model not in SUPPORTED_MODELS:
        raise Exception("Invalid model config for this fusion algorithm")

    current_module = globals().get('__package__')

    model_module = import_module('{}.model_{}'.format(current_module, model))
    method = getattr(model_module, 'get_model_config')

    return method(folder_configs, dataset, is_agg, party_id=0)
