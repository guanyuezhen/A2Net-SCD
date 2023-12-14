import torch.utils.data
import numpy as np
import albumentations as A
from albumentations.pytorch import ToTensorV2
from PIL import Image
import random


def Color2Index(ColorLabel, colormap2label=None, num_classes=None):
    data = ColorLabel.astype(np.int32)
    idx = (data[:, :, 0] * 256 + data[:, :, 1]) * 256 + data[:, :, 2]
    IndexMap = colormap2label[idx]
    IndexMap = IndexMap * (IndexMap < num_classes)
    return IndexMap


def Index2Color(pred, ST_COLORMAP=None):
    colormap = np.asarray(ST_COLORMAP, dtype='uint8')
    x = np.asarray(pred, dtype='int32')
    return colormap[x, :]


class Dataset(torch.utils.data.Dataset):
    '''
    Class to load the dataset
    '''

    def __init__(self, dataset, file_name='SECOND', data_root='data/', transform=None):
        """
        dataset: dataset name, e.g. NJU2K_NLPR_train
        file_root: root of data_path, e.g. ./data/
        """
        if file_name == 'SECOND':
            self.num_classes = 7
            self.ST_COLORMAP = [[255, 255, 255], [0, 0, 255], [128, 128, 128], [0, 128, 0], [0, 255, 0], [128, 0, 0],
                                [255, 0, 0]]
            self.ST_CLASSES = ['unchanged', 'water', 'ground', 'low vegetation', 'tree', 'building', 'sports field']
            self.height = 512
            self.width = 512
        elif file_name == 'LandsatSCD':
            self.num_classes = 5
            self.ST_COLORMAP = [[255, 255, 255], [0, 155, 0], [255, 165, 0], [230, 30, 100], [0, 170, 240]]
            self.ST_CLASSES = ['No change', 'Farmland', 'Desert', 'Building', 'Water']
            self.height = 416
            self.width = 416
        self.colormap2label = np.zeros(256 ** 3)
        for i, cm in enumerate(self.ST_COLORMAP):
            self.colormap2label[(cm[0] * 256 + cm[1]) * 256 + cm[2]] = i

        self.file_list = open(data_root + '/' + dataset + '/list/' + dataset + '.txt').read().splitlines()
        self.pre_images = [data_root + '/' + dataset + '/im1/' + x for x in self.file_list]
        self.post_images = [data_root + '/' + dataset + '/im2/' + x for x in self.file_list]
        self.pre_gts = [data_root + '/' + dataset + '/label1/' + x for x in self.file_list]
        self.post_gts = [data_root + '/' + dataset + '/label2/' + x for x in self.file_list]
        self.transform = transform
        if transform:
            self.train_transforms_all = A.Compose([
                A.Flip(p=0.5),
                A.Transpose(p=0.5),
                A.Rotate(45, p=0.3),
                A.ShiftScaleRotate(p=0.3),
                A.RandomSizedCrop(min_max_height=(self.height, self.width),
                                  width=self.height, height=self.width, w2h_ratio=0.8, p=0.3),
            ], additional_targets={'image1': 'image', 'mask1': 'mask'})
            self.train_transforms_pre_image = A.Compose(
                [A.OneOf([
                    A.GaussNoise(p=1),
                    A.HueSaturationValue(p=1),
                    A.RandomBrightnessContrast(p=1),
                    A.RandomGamma(p=1),
                    A.Emboss(p=1),
                    A.MotionBlur(p=1),
                ], p=0.8)])
            self.train_transforms_post_image = A.Compose(
                [A.OneOf([
                    A.GaussNoise(p=1),
                    A.HueSaturationValue(p=1),
                    A.RandomBrightnessContrast(p=1),
                    A.RandomGamma(p=1),
                    A.Emboss(p=1),
                    A.MotionBlur(p=1),
                ], p=0.8)])
        self.normalize_image = A.Compose([
            A.Normalize()
        ], additional_targets={'image1': 'image'})
        self.to_tensor = A.Compose([
            ToTensorV2()
        ], additional_targets={'image1': 'image', 'mask1': 'mask'})

    def __len__(self):
        return len(self.pre_images)

    @classmethod
    def load(cls, filename):
        """Open image and convert image to array."""

        img = Image.open(filename)
        img = np.array(img)

        return img

    def __getitem__(self, idx):
        pre_image_path = self.pre_images[idx]
        post_image_path = self.post_images[idx]
        pre_label_path = self.pre_gts[idx]
        post_label_path = self.post_gts[idx]
        #
        pre_image = self.load(pre_image_path)
        post_image = self.load(post_image_path)
        pre_label = self.load(pre_label_path)
        post_label = self.load(post_label_path)
        pre_label = Color2Index(pre_label, self.colormap2label, self.num_classes)
        post_label = Color2Index(post_label, self.colormap2label, self.num_classes)
        #
        if self.transform:
            sample = self.train_transforms_all(image=pre_image, image1=post_image, mask=pre_label, mask1=post_label)
            pre_image, post_image, pre_label, post_label = (
                sample['image'], sample['image1'], sample['mask'], sample['mask1'])
            sample = self.train_transforms_pre_image(image=pre_image)
            pre_image = sample['image']
            sample = self.train_transforms_post_image(image=post_image)
            post_image = sample['image']
            if random.choice([0, 1]):
                pre_image, post_image = post_image, pre_image
                pre_label, post_label = post_label, pre_label

        sample = self.normalize_image(image=pre_image, image1=post_image)
        pre_image, post_image = sample['image'], sample['image1']
        sample = self.to_tensor(image=pre_image, image1=post_image, mask=pre_label, mask1=post_label)
        pre_image_tensor, post_image_tensor, pre_label_tensor, post_label_tensor = sample['image'].contiguous(), \
            sample['image1'].contiguous(), sample['mask'].contiguous(), sample['mask1'].contiguous()

        return pre_image_tensor, post_image_tensor, \
            pre_label_tensor.unsqueeze(dim=0), post_label_tensor.unsqueeze(dim=0), self.file_list[idx]

    def get_img_info(self, idx):
        name = self.file_list[idx]
        return {"name": name}
