import torch
import torch.nn.functional as F
from graph_dataset_gen import Mydataset
from dgdnn import DGDNN
from torch_geometric.logging import log
import torch.distributions
import numpy as np
import matplotlib.pyplot as plt
import random
from matplotlib import cm
from matplotlib import axes
import seaborn as sns
import sklearn.preprocessing as skp
from sklearn.metrics import matthews_corrcoef, f1_score

# Configure the device for running the model on GPU or CPU
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Configure the default variables // # these can be tuned // # examples
sedate = ['2013-01-01', '2014-12-31']  # these can be tuned
val_sedate = ['2015-01-01', '2015-06-30'] # these can be tuned
test_sedate = ['2015-07-01', '2017-12-31'] # these can be tuned
market = ['NASDAQ', 'NYSE', 'SSE'] # can be changed
dataset_type = ['Train', 'Validation', 'Test']
com_path = ['/content/drive/MyDrive/Raw_Data/Stock_Markets/NYSE_NASDAQ/NASDAQ.csv',
            '/content/drive/MyDrive/Raw_Data/Stock_Markets/NYSE_NASDAQ/NYSE.csv',
            '/content/drive/MyDrive/Raw_Data/Stock_Markets/NYSE_NASDAQ/NYSE_missing.csv']
des = '/content/drive/MyDrive/Raw_Data/Stock_Markets/NYSE_NASDAQ/raw_stock_data/stocks_indicators/data'
directory = "/content/drive/MyDrive/Raw_Data/Stock_Markets/NYSE_NASDAQ/raw_stock_data/stocks_indicators/data/google_finance"

NASDAQ_com_list = []
NYSE_com_list = []
NYSE_missing_list = []
com_list = [NASDAQ_com_list, NYSE_com_list, NYSE_missing_list]
for idx, path in enumerate(com_path):
    with open(path) as f:
        file = csv.reader(f)
        for line in file:
            com_list[idx].append(line[0])  # append first element of line if each line is a list
NYSE_com_list = [com for com in NYSE_com_list if com not in NYSE_missing_list]

diffusion_size = [110, 256, 512, 540, 560, 400, 320]
linear_size = [256, 310, 512, 400, 540, 380, 560, 350, 400, 300, 320, 256]
decoupled_size = [310+110, 256, 400+256, 512, 380+512, 1024, 350+1024, 1200, 300+1200, 1300, 256+1300, 1024]
mlp_size = [1024, 512, 256, 2] 
layers, num_nodes, expansion_step = 6, 1026, 7


# Generate datasets
train_dataset = MyDataset(directory, des, market[0], NASDAQ_com_list, sedate[0], sedate[1], 21, dataset_type[0])
validation_dataset = MyDataset(directory, des, market[0], NASDAQ_com_list, sedate[0], sedate[1], 21, dataset_type[0])
test_dataset = MyDataset(directory, des, market[0], NASDAQ_com_list, sedate[0], sedate[1], 21, dataset_type[0])


# Define model
model = DGDNN(diffusion_size, linear_size, decoupled_size, mlp_size, layers, num_nodes, expansion_step)

# Pass model GPU
model = model.to(device)

# Define optimizer and objective function
def theta_regularizer(theta):
    row_sums = torch.sum(theta, dim=-1)
    ones = torch.ones_like(row_sums)
    return torch.sum(torch.abs(row_sums - ones))

def neighbor_distance_regularizer(theta):
    box = torch.sum(theta, dim=-1)
    result = torch.zeros_like(theta)

    for idx, row in enumerate(theta):
        for i, j in enumerate(row):
            result[idx, i] = i * j

    result_sum = torch.sum(result, dim=1)
    return torch.sum(result / result_sum[:, None])

optimizer = torch.optim.Adam(model.parameters(), lr=2e-4)


# Define training process & validation process & testing process

epochs = 600
model.reset_parameters()

# Training
for epoch in range(epochs):
    model.train()

    objective_total = 0
    acc = 0

    for sample in train_dataset:
        X = sample['X'].to(device)  # node feature tensor
        A = sample['A'].to(device)  # adjacency tensor
        C = sample['Y'].long()
        C = C.to(device)  # label vector

        objective = F.cross_entropy(model(X, A), C)
        objective += theta_regularizer(model.theta) - 0.0029 * neighbor_distance_regularizer(model.theta)

        objective_total += objective

    objective_average = objective_total / len(train_dataset)
    objective_average.backward()
    optimizer.step()
    optimizer.zero_grad()

    # If performance progress of the model is required
    #model.eval()
    #for sample in train_dataset:
        #X = sample['X'].to(device)  # node feature tensor
        #A = sample['A'].to(device)  # adjacency tensor
        #C = sample['Y'].long()
        #C = C.to(device)  # label vector

        #out = model(X, A).argmax(dim=1)
        #acc += int((out == C).sum())


    if epoch % 10 == 0:
        print(f'Epoch {epoch}: {objective_average.item()}')
        print('ACC: ', acc / ( len(train_dataset) * C.shape[0]))

# Validation
model.eval()

# Define evaluation metrics
# ACC, MCC, and F1
acc = 0
f1 = 0
mcc = 0

for idx, sample in enumerate(validation_dataset):

    X = sample['X']  # node feature tensor
    A = sample['A']  # adjacency tensor
    C = sample['Y']  # label vector
    out = model(X, A).argmax(dim=1)

    acc += int((out == C).sum())
    f1 += f1_score(C, out.cpu().numpy())
    mcc += matthews_corrcoef(C, out.cpu().numpy())

print(acc / (len(validation_dataset) * C.shape[0]))
print(f1 / len(validation_dataset))
print(mcc/ len(validation_dataset))

# Test

acc = 0
f1 = 0
mcc = 0

for idx, sample in enumerate(test_dataset):
    X = sample['X']  # node feature tensor
    A = sample['A']  # adjacency tensor
    C = sample['Y']  # label vector
    out = model(X, A).argmax(dim=1)

    acc += int((out == C).sum())
    f1 += f1_score(C, out.cpu().numpy())
    mcc += matthews_corrcoef(C, out.cpu().numpy())

print(acc / (len(test_dataset) * C.shape[0]))
print(f1 / len(test_dataset))
print(mcc / len(test_dataset))
