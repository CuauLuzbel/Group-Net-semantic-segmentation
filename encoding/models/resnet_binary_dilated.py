import torch.nn as nn
import math
import torch.utils.model_zoo as model_zoo
import torch
import numpy as np
from .new_layers import self_conv, Q_A
import torch.nn.init as init



def conv3x3(in_planes, out_planes, stride=1, padding=1, dilation=1):
    "3x3 convolution with padding"
    return self_conv(in_planes, out_planes, kernel_size=3, stride=stride,
                     padding=padding, dilation=dilation, bias=False)


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, num_bases, inplanes, planes, stride=1, dilation=1, downsample=None, previous_dilation=1, add_gate=True):
        super(BasicBlock, self).__init__()
        self.num_bases = num_bases
        self.add_gate = add_gate
        self.relu = nn.ReLU()
        if isinstance(dilation, list):
            for ratio in dilation:
                self.conv1 = nn.ModuleList([conv3x3(inplanes, planes, stride=stride, padding=ratio, dilation=ratio) for i in range(num_bases)])       
        else:
            self.conv1 = nn.ModuleList([conv3x3(inplanes, planes, stride=stride, padding=dilation, dilation=dilation) for i in range(num_bases)])              
        self.bn1 = nn.ModuleList([nn.BatchNorm2d(planes) for i in range(num_bases)])

        if isinstance(previous_dilation, list):
            for ratio in previous_dilation:
                self.conv2 = nn.ModuleList([conv3x3(planes, planes, padding=ratio, dilation=ratio) for i in range(num_bases)])
        else:
            self.conv2 = nn.ModuleList([conv3x3(planes, planes, padding=previous_dilation, dilation=previous_dilation) for i in range(num_bases)])
        self.bn2 = nn.ModuleList([nn.BatchNorm2d(planes) for i in range(num_bases)])
        self.downsample = downsample
        self.scales = nn.ParameterList([nn.Parameter(torch.rand(1).cuda(), requires_grad=True) for i in range(num_bases)])
        if add_gate:
            self.block_gate = nn.Parameter(torch.rand(1).cuda(), requires_grad=True)


    def forward(self, input_bases, input_mean):

        final_output = None
        output_bases = []

        if self.add_gate:

            for base, conv1, conv2, bn1, bn2, scale in zip(input_bases, self.conv1, self.conv2, self.bn1, self.bn2, self.scales):

                x = nn.Sigmoid()(self.block_gate) * base + (1.0 - nn.Sigmoid()(self.block_gate)) * input_mean

                if self.downsample is not None:
                    x = Q_A.apply(x)
                    residual = self.downsample(x)
                else:
                    residual = x
                    x = Q_A.apply(x)

                out = conv1(x)
                out = self.relu(out)
                out = bn1(out)
                out += residual

                out_new = Q_A.apply(out)
                out_new = conv2(out_new)
                out_new = self.relu(out_new)
                out_new = bn2(out_new)
                out_new += out

                output_bases.append(out_new)
                      
                if final_output is None:
                    final_output = scale * out_new
                else:
                    final_output += scale * out_new

        else:

            for conv1, conv2, bn1, bn2, scale in zip(self.conv1, self.conv2, self.bn1, self.bn2, self.scales):

                if self.downsample is not None:
                    x = Q_A.apply(input_mean)
                    residual = self.downsample(x)
                else:
                    residual = input_mean
                    x = Q_A.apply(input_mean)

                out = conv1(x)
                out = self.relu(out)
                out = bn1(out)
                out += residual

                out_new = Q_A.apply(out)
                out_new = conv2(out_new)
                out_new = self.relu(out_new)
                out_new = bn2(out_new)
                out_new += out

                output_bases.append(out_new)
                      
                if final_output is None:
                    final_output = scale * out_new
                else:
                    final_output += scale * out_new


        return output_bases, final_output



class downsample_layer(nn.Module):
    def __init__(self, inplanes, planes, kernel_size=1, stride=1, bias=False):
        super(downsample_layer, self).__init__()
        self.conv = self_conv(inplanes, planes, kernel_size=kernel_size, stride=stride, bias=False)
        self.batch_norm = nn.BatchNorm2d(planes)

    def forward(self, x):
        x = self.conv(x)
        x = self.batch_norm(x)
        return x



class ResNet(nn.Module):

    def __init__(self, block, layers, num_classes=1000, dilated=False, multi_grid=False,
                 deep_base=True, norm_layer=nn.BatchNorm2d):
        self.inplanes = 64
        self.num_bases = 5     
        super(ResNet, self).__init__()
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0], add_gate=False)
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        if dilated:
            self.layer3 = self._make_layer(block, 256, layers[2], stride=1,
                                           dilation=[2,3,4,5,6])
            if multi_grid:
                self.layer4 = self._make_layer(block, 512, layers[3], stride=1,
                                               dilation=4,
                                               multi_grid=True)
            else:
                self.layer4 = self._make_layer(block, 512, layers[3], stride=1,
                                               dilation=[6,7,8,9,10])
        else:
            self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
            self.layer4 = self._make_layer(block, 512, layers[3], stride=2)


        self.avgpool = nn.AvgPool2d(7)
        self.fc = nn.Linear(512 * block.expansion, num_classes)


    def _make_layer(self, block, planes, blocks, stride=1, dilation=1, multi_grid=False, add_gate=True):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = downsample_layer(self.inplanes, planes * block.expansion, 
                          kernel_size=1, stride=stride, bias=False)

        layers = nn.ModuleList([])

        multi_dilations = [4, 8, 16]
        if multi_grid:
            layers.append(block(self.num_bases, self.inplanes, planes, stride, dilation=multi_dilations[0],
                                downsample=downsample, previous_dilation=dilation, add_gate=add_gate))
        elif dilation == 1 or dilation == 2:
            layers.append(block(self.num_bases, self.inplanes, planes, stride, dilation=1,
                                downsample=downsample, previous_dilation=dilation, add_gate=add_gate))
        elif dilation == 4:
            layers.append(block(self.num_bases, self.inplanes, planes, stride, dilation=2,
                                downsample=downsample, previous_dilation=dilation, add_gate=add_gate))

        elif isinstance(dilation, list):
            layers.append(block(self.num_bases, self.inplanes, planes, stride, dilation=dilation,
                                downsample=downsample, previous_dilation=dilation, add_gate=add_gate))

        else:
            raise RuntimeError("=> unknown dilation size: {}".format(dilation))

        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            if multi_grid:
                layers.append(block(self.num_bases, self.inplanes, planes, dilation=multi_dilations[i],
                                    previous_dilation=dilation))
            else:
                layers.append(block(self.num_bases, self.inplanes, planes, dilation=dilation, previous_dilation=dilation))

        return layers


    def forward(self, x):
        x = self.conv1(x)
        x = self.maxpool(x)
        x = self.bn1(x)

        sep_out = None
        sum_out = x
        for layer in self.layer1: 
            sep_out, sum_out = layer(sep_out, sum_out)

        for layer in self.layer2:
            sep_out, sum_out = layer(sep_out, sum_out)

        for layer in self.layer3:
            sep_out, sum_out = layer(sep_out, sum_out)

        for layer in self.layer4:
            sep_out, sum_out = layer(sep_out, sum_out)

        out = self.avgpool(sum_out)
        out = out.view(out.size(0), -1)
        out = self.fc(out)

        return out


def resnet18(pretrained=True, root='', **kwargs):
    """Constructs a ResNet-18 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(BasicBlock, [2, 2, 2, 2], deep_base=False, **kwargs)
    if pretrained:
        load_dict = torch.load('./pretrained.pth.tar')['state_dict']
        model_dict = model.state_dict()
        model_keys = model_dict.keys()
        for name, param in load_dict.items():
            if name.replace('module.', '') in model_keys:
                model_dict[name.replace('module.', '')] = param  
        model.load_state_dict(model_dict)  
    return model


def resnet34(pretrained=True, root='', **kwargs):
    """Constructs a ResNet-34 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(BasicBlock, [3, 4, 6, 3], deep_base=False, **kwargs)
    if pretrained:
        load_dict = torch.load('./pretrained.pth.tar')['state_dict']
        model_dict = model.state_dict()
        model_keys = model_dict.keys()
        for name, param in load_dict.items():
            if name.replace('module.', '') in model_keys:
                model_dict[name.replace('module.', '')] = param    
        model.load_state_dict(model_dict)  
    return model


def resnet50(pretrained=True, **kwargs):
    """Constructs a ResNet-50 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(Bottleneck, [3, 4, 6, 3], deep_base=False, **kwargs)
    if pretrained:
        load_dict = torch.load('./pretrained.pth.tar')['state_dict']
        model_dict = model.state_dict()
        model_keys = model_dict.keys()
        for name, param in load_dict.items():
            if name.replace('module.', '') in model_keys:
                model_dict[name.replace('module.', '')] = param    
        model.load_state_dict(model_dict)  
    return model
