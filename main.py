import os
import argparse

import matplotlib.pyplot as plt

import torch
import torchvision
from torch.utils.data import  DataLoader
from torchvision import transforms

import wandb

from Dataloaders.utkf_dataloader import UTKface
from Dataloaders.wine_dataloader import WineQuality
from model import AgeModel, WineModel
from losses import IVLoss
from train import Trainer

# expirement settings
from params import d_params
from params import n_params

from utils import str_to_bool, average_noise_mean


# Main 

if __name__ == "__main__":

    # Parse arguments from the commandline
    
    parser =  argparse.ArgumentParser(description=" A parser for baseline uniform noisy experiment")
    parser.add_argument("--exp_settings", type=str, default="0")
    parser.add_argument("--noise_settings", type=str, default="0")
    parser.add_argument("--noise_params", type=str, default="0")
    parser.add_argument("--estim_noise_params", type=str, default="0")    

    args = parser.parse_args()

    # Define global varriables.

    exp_settings = args.exp_settings.split(",")
    noise_settings = args.noise_settings.split(",")

    # Extract commandline parameters

    
    tag = exp_settings[0]
    seed = exp_settings[1]
    dataset = exp_settings[2]
    normalize = exp_settings[3]
    loss_type = exp_settings[4]
    try:
        epsilon = exp_settings[5]   # a dirty way to handle epsilon value if it is missing. # will be handled if similar cases appeared.
    except:
        pass
    
    model_type = exp_settings[6]
    average_mean_factor = exp_settings[7]
    
    noise = noise_settings[0]
    noise_type = noise_settings[1]
    is_estim_noise_params = noise_settings[2]
    hetero_scale = noise_settings[3]
    distributions_ratio_p = noise_settings[4]
    threshold_value = noise_settings[5]
    
  
    # Assert the commandline arguments values.
    messages = {"bool":":argument is not boolean.", "datatype":"datatype is not supported.", "value":"argument value is not recognized."}

    assert isinstance(float(seed), float), "Argument: seed: " + messages.get('datatype')
    assert dataset in ["utkf","wine"], "Argument: dataset: " + messages.get('value')
    assert isinstance( str_to_bool(normalize), bool), "Argument: normalize: " + messages.get('bool')
    assert loss_type in ["mse", "iv", "biv"], "Argument: loss_type: " + messages.get('value')
    assert epsilon.replace('.','',1).isdigit() , "Argument: epsilon: " + messages.get('datatype')
    assert model_type in ["vanilla_ann","vanilla_cnn", "resnet"], "Argument: model_type: " + messages.get('value')
    assert average_mean_factor.replace('.','',1).replace('-','',1).isdigit(), "Argument: average_mean_factor: "+ messages.get('value')

    assert isinstance( str_to_bool(noise), bool), "Argument: noise: " + messages.get('bool')
    assert noise_type in ["uniform","gamma"], "Argument: noise_type: " + messages.get('value')
    assert isinstance( str_to_bool(is_estim_noise_params), bool), "Argument: estimate_noise_params: " + messages.get('bool')
    assert float(hetero_scale)==-1 or float(hetero_scale)>=0 and float(hetero_scale)<=1 , "Argument: hetero_scale: "+ messages.get('value')
    assert float(distributions_ratio_p)>=0 and float(distributions_ratio_p)<=1 , "Argument: distributions_ratio_p: "+ messages.get('value')
    assert threshold_value.replace('.','',1).replace('-','',1).isdigit(), "Argument: threshold_value: " + messages.get('datatype')


    
    # Convert commandline arguments to appropriate datatype.

    seed = int(seed)
    normalize = str_to_bool(normalize)
    epsilon = float(epsilon)
    average_mean_factor = float(average_mean_factor)
    is_noise = str_to_bool(noise)
    is_estim_noise_params = str_to_bool(is_estim_noise_params)
    hetero_scale = float(hetero_scale)
    maximum_hetero = True if hetero_scale>=0 else False 
    distributions_ratio_p = float(distributions_ratio_p)
    threshold_value = float(threshold_value)
    is_noise_threshold = True if threshold_value>=0 else False


# Handle distributions parameters

    if is_estim_noise_params:
        noise_params = args.noise_params.split(",")
        for item in noise_params: assert item.replace('.','',1).replace('-','',1).isdigit() , "Argument: noise_params: " + messages.get('datatype')
        noise_params = list(map(lambda x: float(x), noise_params))
    else:
        estim_noise_params = args.estim_noise_params.split(",")
        for item in estim_noise_params: assert item.replace('.','',1).replace('-','',1).isdigit() , "Argument: estim_noise_params: " + messages.get('datatype')
        estim_noise_params =  list(map(lambda x: float(x), estim_noise_params))


    

    # Get Wandb tags
    tag = [tag,]
    # Initiate wandb client.
    wandb.init(project="iv_deep_learning",tags=tag , entity="montreal_robotics")
    # Get the api key from the environment variables.
    api_key = os.environ.get('WANDB_API_KEY')
    # login to my wandb account.
    wandb.login(api_key)

    # Set expirement seed
    torch.manual_seed(seed)
    # Set experiment id
    exp_id = str(distributions_ratio_p)

    # Define the dataset
    if is_estim_noise_params:
        if average_mean_factor>=0 and len(estim_noise_params)//2==2 and distributions_ratio_p<1:
            estim_noise_params[1] = average_noise_mean(average_mean_factor,estim_noise_params[0],distributions_ratio_p)
        dist_data = {"coin_fairness":distributions_ratio_p,"is_params_est":is_estim_noise_params, "is_vmax":maximum_hetero, "vmax_scale":hetero_scale ,"data":estim_noise_params}
    else:
        dist_data = {"coin_fairness":distributions_ratio_p,"is_params_est":is_estim_noise_params, "data":noise_params}


    if dataset == "utkf":

        d_path = d_params.get('d_path')
        tr_size = d_params.get('tr_batch_size')
        tst_size = d_params.get('test_batch_size')
        learning_rate = n_params.get('lr')
        epochs = n_params.get('epochs')

        trans= torchvision.transforms.Compose([transforms.ToTensor()])

        train_data = UTKface(d_path, transform= trans, train= True, model= model_type, noise=is_noise, noise_type=noise_type, distribution_data = \
                                            dist_data, normalize=normalize, noise_threshold = is_noise_threshold, threshold_value = threshold_value) 
        test_data = UTKface(d_path, transform= trans, train= False, model= model_type, normalize=normalize)


    elif dataset == "wine":

        d_path = d_params.get('wine_path')
        tr_size = d_params.get('wine_tr_batch_size')
        tst_size = d_params.get('wine_test_batch_size')
        learning_rate = n_params.get('wine_lr')
        epochs = n_params.get('epochs')

        train_data = WineQuality(d_path, train= True, model= model_type, noise=is_noise, noise_type=noise_type, distribution_data = \
                                        dist_data, normalize=normalize, noise_threshold = is_noise_threshold, threshold_value = threshold_value) 
        test_data = WineQuality(d_path, train= False, model= model_type, normalize=normalize)

        
    # Load the data
    train_loader = DataLoader(train_data, batch_size=tr_size)
    test_loader = DataLoader(test_data, batch_size=tst_size)

    if model_type =="vanilla_ann" and dataset=='wine':
        model = WineModel()
        print("#################### Model is:{} ####################".format(model_type))
    elif model_type == "resnet" and dataset == 'utkf':
        model = torchvision.models.resnet18(pretrained=False)
        model.fc = torch.nn.Linear(512,1)   # converting resnet to a regression layer
        print("#################### Model is:{} ####################".format(model_type))
    elif model_type == "vanilla_cnn" and dataset == 'utkf':
        model = AgeModel()
        print("#################### Model is:{} ####################".format(model_type))
    else:
        raise ValueError(" Model is not recognized or the dataset and the model are not compatible with each other.")


    # Optimizer
    optimz = torch.optim.Adam(model.parameters(), lr=learning_rate)

    # Loss function
    if loss_type == "iv":
        loss = IVLoss(epsilon=epsilon, avg_batch=False)
    elif loss_type == "biv":
        loss = IVLoss(epsilon=epsilon, avg_batch=True)
    else:
        loss = torch.nn.MSELoss()


 
    # Trainer
    trainer = Trainer(experiment_id=exp_id, train_loader= train_loader, test_loader= test_loader, \
        model=model, loss= loss, optimizer= optimz, epochs = epochs)


    # Call wandb to log model performance.
    wandb.watch(model)
    # train the model
    trainer.train(alogrithm=loss_type)


