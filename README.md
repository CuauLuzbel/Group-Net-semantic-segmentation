# Structured Binary Neural Networks for Image Recognition

created by [Bohan Zhuang](https://sites.google.com/view/bohanzhuang)

## [External code](http://hangzh.com/PyTorch-Encoding/)

- We use the [**PyTorch-Encoding**](http://hangzh.com/PyTorch-Encoding/) as the code base. Please refer to Pytorch-Encoding for detailed instructions of installation and usage. Note that you **must** install pytorch 1.0 from source and you need to solve the bug via this [link](https://github.com/huanghoujing/PyTorch-Encoding/blob/master/Fix_Bugs_of_Pytorch_Encoding.md). 


## Training 

- run python train.py. We use the binary backbone pretrained on ImageNet as initialization. The pretrained binary backbone can be downloaded at [image classification repository](https://github.com/zhuangbohan/Group-Net-image-classification).


- In particular, to make consistent with the conference version, we employ the learnt "scales" by default. For example, download the resnet18_with_softgates.pth.tar as initialization. But in the journal version, we omit these scales and directly use averaging.


## Testing
python test.py

## Citations

```
@article{zhuang2019structured,
  title={Structured Binary Neural Networks for Image Recognition},
  author={Zhuang, Bohan and Shen, Chunhua and Tan, Mingkui and Liu, Lingqiao and Reid, Ian},
  journal={arXiv preprint arXiv:1909.09934},
  year={2019}
}

```

## License

For academic use, this project is licensed under the 2-clause BSD License - see the LICENSE file for details. For commercial use, please contact the authors. 
