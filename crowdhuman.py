# -*- coding: utf-8 -*-
'''
@Time          : 2020/05/06 21:09
@Author        : Tianxiaomo
@File          : dataset.py
@Noice         :
@Modificattion :
    @Author    :
    @Time      :
    @Detail    :

'''
import json
import os
import random
import cv2
import numpy as np
import torch
from torch.utils.data.dataset import Dataset
def rand_uniform_strong(min, max):
    if min > max:
        swap = min
        min = max
        max = swap
    return random.random() * (max - min) + min


def rand_scale(s):
    scale = rand_uniform_strong(1, s)
    if random.randint(0, 1) % 2:
        return scale
    return 1. / scale


def rand_precalc_random(min, max, random_part):
    if max < min:
        swap = min
        min = max
        max = swap
    return (random_part * (max - min)) + min


def fill_truth_detection(bboxes, num_boxes, classes, flip, dx, dy, sx, sy, net_w, net_h):
    if bboxes.shape[0] == 0:
        return bboxes, 10000
    np.random.shuffle(bboxes)
    # gt左移
    bboxes[:, 0] -= dx
    bboxes[:, 2] -= dx
    # gt上移动
    bboxes[:, 1] -= dy
    bboxes[:, 3] -= dy

    # 将移动后的gt限制在新的图片大小之内不能越界
    # index = 1 if bboxes[:4] != 1 else 0
    # print(index)
    for i, box in enumerate(bboxes):
        if box[4] != 1:
            bboxes[i, 0] = np.clip(bboxes[i, 0], 0, sx)
            bboxes[i, 2] = np.clip(bboxes[i, 2], 0, sx)
            bboxes[i, 1] = np.clip(bboxes[i, 1], 0, sy)
            bboxes[i, 3] = np.clip(bboxes[i, 3], 0, sy)



    # bboxes[:, 0] = np.clip(bboxes[:, 0], 0, sx)
    # bboxes[:, 2] = np.clip(bboxes[:, 2], 0, sx)
    # bboxes[:, 1] = np.clip(bboxes[:, 1], 0, sy)
    # bboxes[:, 3] = np.clip(bboxes[:, 3], 0, sy)

    # 得到一些不合格的gtbox并删除
    #
    out_box = list(np.where(((bboxes[:, 1] >= sy - (bboxes[:, 3] - bboxes[:, 1]) * 0.1) & (bboxes[:, 3] >= sy)) |
                            ((bboxes[:, 0] >= sx - (bboxes[:, 2] - bboxes[:, 0]) * 0.3) & (bboxes[:, 2] >= sx)) |
                            ((bboxes[:, 1] <= 0) & (bboxes[:, 3] <= 0 + (bboxes[:, 3] - bboxes[:, 1]) * 0.4)) |
                            ((bboxes[:, 0] <= 0) & (bboxes[:, 2] <= 0 + (bboxes[:, 2] - bboxes[:, 0]) * 0.3)))[0])
    list_box = list(range(bboxes.shape[0]))  # gt的index
    for i in out_box:
        list_box.remove(i)
    bboxes = bboxes[list_box]

    if bboxes.shape[0] == 0:
        return bboxes, 10000

    # classes, num_boxes = 80, 60||排除多余的类别和限制gt的个数
    bboxes = bboxes[np.where((bboxes[:, 4] < classes) & (bboxes[:, 4] >= 0))[0]]

    if bboxes.shape[0] > num_boxes:
        bboxes = bboxes[:num_boxes]
    # 得到裁剪之后的gt的最小边长
    min_w_h = np.array([bboxes[:, 2] - bboxes[:, 0], bboxes[:, 3] - bboxes[:, 1]]).min()

    # net_h, net_w = 608， 608 输入网络的img大小
    # 根据比例对新gt进行等比缩放
    bboxes[:, 0] *= (net_w / sx)
    bboxes[:, 2] *= (net_w / sx)
    bboxes[:, 1] *= (net_h / sy)
    bboxes[:, 3] *= (net_h / sy)

    if flip:  # 是否水平翻转
        temp = net_w - bboxes[:, 0]
        bboxes[:, 0] = net_w - bboxes[:, 2]
        bboxes[:, 2] = temp

    return bboxes, min_w_h


def rect_intersection(a, b):
    minx = max(a[0], b[0])
    miny = max(a[1], b[1])

    maxx = min(a[2], b[2])
    maxy = min(a[3], b[3])
    return [minx, miny, maxx, maxy]


def image_data_augmentation(mat, w, h, pleft, ptop, swidth, sheight, flip, dhue, dsat, dexp, gaussian_noise, blur,
                            truth):
    try:
        img = mat
        oh, ow, _ = img.shape
        pleft, ptop, swidth, sheight = int(pleft), int(ptop), int(swidth), int(sheight)
        # crop
        src_rect = [pleft, ptop, swidth + pleft, sheight + ptop]  # x1,y1,x2,y2
        img_rect = [0, 0, ow, oh]
        new_src_rect = rect_intersection(src_rect, img_rect)  # 交集

        dst_rect = [max(0, -pleft), max(0, -ptop), max(0, -pleft) + new_src_rect[2] - new_src_rect[0],
                    max(0, -ptop) + new_src_rect[3] - new_src_rect[1]]
        # cv2.Mat sized

        if (src_rect[0] == 0 and src_rect[1] == 0 and src_rect[2] == img.shape[0] and src_rect[3] == img.shape[1]):
            sized = cv2.resize(img, (w, h), cv2.INTER_LINEAR)
        else:
            cropped = np.zeros([sheight, swidth, 3])
            cropped[:, :, ] = np.mean(img, axis=(0, 1))

            cropped[dst_rect[1]:dst_rect[3], dst_rect[0]:dst_rect[2]] = \
                img[new_src_rect[1]:new_src_rect[3], new_src_rect[0]:new_src_rect[2]]

            # resize
            sized = cv2.resize(cropped, (w, h), cv2.INTER_LINEAR)

        # flip
        if flip:
            # cv2.Mat cropped
            sized = cv2.flip(sized, 1)  # 0 - x-axis, 1 - y-axis, -1 - both axes (x & y)

        # HSV augmentation
        # cv2.COLOR_BGR2HSV, cv2.COLOR_RGB2HSV, cv2.COLOR_HSV2BGR, cv2.COLOR_HSV2RGB
        if dsat != 1 or dexp != 1 or dhue != 0:
            if img.shape[2] >= 3:
                hsv_src = cv2.cvtColor(sized.astype(np.float32), cv2.COLOR_RGB2HSV)  # RGB to HSV
                hsv = cv2.split(hsv_src)
                hsv[1] *= dsat
                hsv[2] *= dexp
                hsv[0] += 179 * dhue
                hsv_src = cv2.merge(hsv)
                sized = np.clip(cv2.cvtColor(hsv_src, cv2.COLOR_HSV2RGB), 0, 255)  # HSV to RGB (the same as previous)
            else:
                sized *= dexp

        if blur:
            if blur == 1:
                dst = cv2.GaussianBlur(sized, (17, 17), 0)
                # cv2.bilateralFilter(sized, dst, 17, 75, 75)
            else:
                ksize = (blur / 2) * 2 + 1
                dst = cv2.GaussianBlur(sized, (ksize, ksize), 0)

            if blur == 1:
                img_rect = [0, 0, sized.cols, sized.rows]
                for b in truth:
                    left = (b.x - b.w / 2.) * sized.shape[1]
                    width = b.w * sized.shape[1]
                    top = (b.y - b.h / 2.) * sized.shape[0]
                    height = b.h * sized.shape[0]
                    roi(left, top, width, height)
                    roi = roi & img_rect
                    dst[roi[0]:roi[0] + roi[2], roi[1]:roi[1] + roi[3]] = sized[roi[0]:roi[0] + roi[2],
                                                                          roi[1]:roi[1] + roi[3]]

            sized = dst

        if gaussian_noise:
            noise = np.array(sized.shape)
            gaussian_noise = min(gaussian_noise, 127)
            gaussian_noise = max(gaussian_noise, 0)
            cv2.randn(noise, 0, gaussian_noise)  # mean and variance
            sized = sized + noise
    except:
        print("OpenCV can't augment image: " + str(w) + " x " + str(h))
        sized = mat

    return sized


def filter_truth(bboxes, dx, dy, sx, sy, xd, yd):
    bboxes[:, 0] -= dx
    bboxes[:, 2] -= dx
    bboxes[:, 1] -= dy
    bboxes[:, 3] -= dy

    #modify:
    for i, box in enumerate(bboxes):
        if box[4] != 1:
            bboxes[i, 0] = np.clip(bboxes[i, 0], 0, sx)
            bboxes[i, 2] = np.clip(bboxes[i, 2], 0, sx)
            bboxes[i, 1] = np.clip(bboxes[i, 1], 0, sy)
            bboxes[i, 3] = np.clip(bboxes[i, 3], 0, sy)
    # bboxes[:, 0] = np.clip(bboxes[:, 0], 0, sx)
    # bboxes[:, 2] = np.clip(bboxes[:, 2], 0, sx)
    #
    # bboxes[:, 1] = np.clip(bboxes[:, 1], 0, sy)
    # bboxes[:, 3] = np.clip(bboxes[:, 3], 0, sy)

    out_box = list(np.where(((bboxes[:, 1] >= sy - (bboxes[:, 3] - bboxes[:, 1]) * 0.1) & (bboxes[:, 3] >= sy)) |
                            ((bboxes[:, 0] >= sx - (bboxes[:, 2] - bboxes[:, 0]) * 0.3) & (bboxes[:, 2] >= sx)) |
                            ((bboxes[:, 1] <= 0) & (bboxes[:, 3] <= 0 + (bboxes[:, 3] - bboxes[:, 1]) * 0.4)) |
                            ((bboxes[:, 0] <= 0) & (bboxes[:, 2] <= 0 + (bboxes[:, 2] - bboxes[:, 0]) * 0.3)))[0])
    list_box = list(range(bboxes.shape[0]))
    for i in out_box:
        list_box.remove(i)
    bboxes = bboxes[list_box]

    bboxes[:, 0] += xd
    bboxes[:, 2] += xd
    bboxes[:, 1] += yd
    bboxes[:, 3] += yd
    return bboxes

def blend_truth_mosaic(out_img, img, bboxes, w, h, cut_x, cut_y, i_mixup,
                       left_shift, right_shift, top_shift, bot_shift):
    left_shift = min(left_shift, w - cut_x)
    top_shift = min(top_shift, h - cut_y)
    right_shift = min(right_shift, cut_x)
    bot_shift = min(bot_shift, cut_y)

    if i_mixup == 0:
        bboxes = filter_truth(bboxes, left_shift, top_shift, cut_x, cut_y, 0, 0)
        out_img[:cut_y, :cut_x] = img[top_shift:top_shift + cut_y, left_shift:left_shift + cut_x]
    if i_mixup == 1:
        bboxes = filter_truth(bboxes, cut_x - right_shift, top_shift, w - cut_x, cut_y, cut_x, 0)
        out_img[:cut_y, cut_x:] = img[top_shift:top_shift + cut_y, cut_x - right_shift:w - right_shift]
    if i_mixup == 2:
        bboxes = filter_truth(bboxes, left_shift, cut_y - bot_shift, cut_x, h - cut_y, 0, cut_y)
        out_img[cut_y:, :cut_x] = img[cut_y - bot_shift:h - bot_shift, left_shift:left_shift + cut_x]
    if i_mixup == 3:
        bboxes = filter_truth(bboxes, cut_x - right_shift, cut_y - bot_shift, w - cut_x, h - cut_y, cut_x, cut_y)
        out_img[cut_y:, cut_x:] = img[cut_y - bot_shift:h - bot_shift, cut_x - right_shift:w - right_shift]

    return out_img, bboxes


def draw_box(img, bboxes):
    for b in bboxes:
        if b[4] == 1:
            img = cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 255, 0), 2)
        else:
            continue
    return img


class CrowdHuman_dataset(Dataset):

    def __init__(self, lable_path, cfg, train=True):
        super(CrowdHuman_dataset, self).__init__()
        if cfg.mixup == 2:
            print("cutmix=1 - isn't supported for Detector")
            raise
        elif cfg.mixup == 2 and cfg.letter_box:
            print("Combination: letter_box=1 & mosaic=1 - isn't supported, use only 1 of these parameters")
            raise

        self.cfg = cfg
        self.train = train
        self.imgs = []
        self.truth = {}
        assert os.path.exists(lable_path)
        with open(lable_path, 'r') as fid:
            lines = fid.readlines()
        train_img_path = os.path.join(cfg.dataset_dir, 'Images/')
        # self.truth = [json.loads(line.strip('\n')) for line in lines]
        self.imgs = [os.path.join(train_img_path, json.loads(line)['ID']+'.jpg') for line in lines]
        # self.truth = [json.loads(line)['gtboxes'] for line in lines]
        for i, line in enumerate(lines):
            self.truth[self.imgs[i]] = list()
            for j , gtbox in enumerate(json.loads(line)['gtboxes']):
                self.truth[self.imgs[i]].append(gtbox['fbox'] + [1])
                self.truth[self.imgs[i]].append(gtbox['hbox'] + [2])
                self.truth[self.imgs[i]].append(gtbox['vbox'] + [3])

        del i, j, line, lines, gtbox, lable_path

    def __len__(self):
        return len(self.truth.keys())

    def __getitem__(self, index):
        if not self.train:
            return self._get_val_item(index)
        # 得到anchor的图片key和gtbox
        img_path = self.imgs[index]
        bboxes = np.array(self.truth.get(img_path), dtype=np.float)
        # xywh2xyxy
        bboxes[:, 2:4] += bboxes[:,:2]
        # (1, 5): [[156.  97. 351. 270.   6.]]
        # 在组合的时候anchor图会被放在第一张
        img = cv2.imread(img_path)
        # print(img.shape)
        # self.cfg.w = img.shape[0]
        # self.cfg.h = img.shape[1]
        # self.cfg.w = random.randint(1900, 2200)
        # self.cfg.h = random.randint(1000, 1200)
        self.cfg.w = random.randint(1000, 1333)
        self.cfg.h = random.randint(600, 800)

        # 得到图片的路径
        print("{} img is {}".format(index, img_path))
        # use_mixup = 3
        use_mixup = self.cfg.mixup

        # 50%的概率不使用use_mixup
        if random.randint(0, 1):
            use_mixup = 0

        if use_mixup == 3:
            min_offset = 0.2  # 最小的抖动
            # self.cfg.h, self.cfg.w = 608, 608
            cut_x = random.randint(int(self.cfg.w * min_offset), int(self.cfg.w * (1 - min_offset)))
            cut_y = random.randint(int(self.cfg.h * min_offset), int(self.cfg.h * (1 - min_offset)))

        r1, r2, r3, r4, r_scale = 0, 0, 0, 0, 0
        dhue, dsat, dexp, flip, blur = 0, 0, 0, 0, 0
        gaussian_noise = 0

        # 结果图片，先创建一个黑色的幕布: (608, 608, 3)
        out_img = np.zeros([self.cfg.h, self.cfg.w, 3])
        out_bboxes = []

        # 1张anchor要和use_mixup张图片进行合并
        for i in range(use_mixup + 1):
            # 如歌当前图片不是anchor图片
            if i != 0:
                # 从train_list中进行随机抽取一张图片，得到图片的gt和完整路径
                img_path = random.choice(list(self.truth.keys()))
                bboxes = np.array(self.truth.get(img_path), dtype=np.float)
                bboxes[:, 2:4] += bboxes[:, :2]
                img_path = os.path.join(self.cfg.dataset_dir, img_path)
                # print("{} img is {}".format(i, img_path))
            # 读取图片并转为RGB格式
            img = cv2.imread(img_path)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # 读出来是None直接跳过，提高代码的健壮性
            if img is None:
                continue

            # origin_height origin_wight origin_channel
            oh, ow, oc = img.shape
            # 得到每个维度的偏移 self.cfg.jitter = 0.2
            dh, dw, dc = np.array(np.array([oh, ow, oc]) * self.cfg.jitter, dtype=np.int)

            # self.cfg.hue self.cfg.saturation self.cfg.exposure =  0.1 1.5 1.5
            # 得到一些有关色域的随机参数
            dhue = rand_uniform_strong(-self.cfg.hue, self.cfg.hue)
            dsat = rand_scale(self.cfg.saturation)
            dexp = rand_scale(self.cfg.exposure)

            # 偏移参数
            pleft = random.randint(-dw, dw)
            pright = random.randint(-dw, dw)
            ptop = random.randint(-dh, dh)
            pbot = random.randint(-dh, dh)

            # self.cfg.flip = 1这里采用了随机翻转
            flip = random.randint(0, 1) if self.cfg.flip else 0

            # 没有采用模糊
            if (self.cfg.blur):
                tmp_blur = random.randint(0, 2)  # 0 - disable, 1 - blur background, 2 - blur the whole image
                if tmp_blur == 0:
                    blur = 0
                elif tmp_blur == 1:
                    blur = 1
                else:
                    blur = self.cfg.blur

            # 没有采用高斯噪声
            if self.cfg.gaussian and random.randint(0, 1):
                gaussian_noise = self.cfg.gaussian
            else:
                gaussian_noise = 0


            # →←和↑↓之后还剩余的宽度和长度swidth, sheight
            swidth = ow - pleft - pright
            sheight = oh - ptop - pbot

            # gt转换,过滤一些不要的box
            truth, min_w_h = fill_truth_detection(bboxes, self.cfg.boxes, self.cfg.classes, flip, pleft, ptop, swidth,
                                                  sheight, self.cfg.w, self.cfg.h)
            if (min_w_h / 8) < blur and blur > 1:  # disable blur if one of the objects is too small
                blur = min_w_h / 8
            # 图像增强
            #ai (758, 1317, 3)
            ai = image_data_augmentation(img, self.cfg.w, self.cfg.h, pleft, ptop, swidth, sheight, flip,
                                         dhue, dsat, dexp, gaussian_noise, blur, truth)

            if use_mixup == 0:  # 不用拼接
                out_img = ai
                out_bboxes = truth
            if use_mixup == 1:  # 只和一张图拼接
                if i == 0:
                    old_img = ai.copy()
                    old_truth = truth.copy()
                elif i == 1:
                    # 采用叠加的方式拼接
                    out_img = cv2.addWeighted(ai, 0.5, old_img, 0.5)
                    out_bboxes = np.concatenate([old_truth, truth], axis=0)

            elif use_mixup == 3:  # 采用左右上下边界拼接的方式, 注意拼接时候的缩放比例,box也要再次缩放
                if flip:
                    tmp = pleft
                    pleft = pright
                    pright = tmp
                #向左平移
                left_shift = int(min(cut_x, max(0, (-int(pleft) * self.cfg.w / swidth))))
                top_shift = int(min(cut_y, max(0, (-int(ptop) * self.cfg.h / sheight))))

                right_shift = int(min((self.cfg.w - cut_x), max(0, (-int(pright) * self.cfg.w / swidth))))
                bot_shift = int(min(self.cfg.h - cut_y, max(0, (-int(pbot) * self.cfg.h / sheight))))

                out_img, out_bbox = blend_truth_mosaic(out_img, ai, truth.copy(), self.cfg.w, self.cfg.h, cut_x,
                                                       cut_y, i, left_shift, right_shift, top_shift, bot_shift)
                out_bboxes.append(out_bbox)
                # print(img_path)
        if use_mixup == 3:
            out_bboxes = np.concatenate(out_bboxes, axis=0)
        out_bboxes1 = np.zeros([self.cfg.boxes, 5])
        out_bboxes1[:min(out_bboxes.shape[0], self.cfg.boxes)] = out_bboxes[:min(out_bboxes.shape[0], self.cfg.boxes)]
        return out_img, out_bboxes1

    def _get_val_item(self, index):
        """
        """
        img_path = self.imgs[index]
        bboxes_with_cls_id = np.array(self.truth.get(img_path), dtype=np.float)
        img = cv2.imread(os.path.join(self.cfg.dataset_dir, img_path))
        # img_height, img_width = img.shape[:2]
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # img = cv2.resize(img, (self.cfg.w, self.cfg.h))
        # img = torch.from_numpy(img.transpose(2, 0, 1)).float().div(255.0).unsqueeze(0)
        num_objs = len(bboxes_with_cls_id)
        target = {}
        # boxes to coco format
        boxes = bboxes_with_cls_id[...,:4]
        boxes[..., 2:] = boxes[..., 2:] - boxes[..., :2]  # box width, box height
        target['boxes'] = torch.as_tensor(boxes, dtype=torch.float32)
        target['labels'] = torch.as_tensor(bboxes_with_cls_id[...,-1].flatten(), dtype=torch.int64)
        target['image_id'] = torch.tensor([get_image_id(img_path)])
        target['area'] = (target['boxes'][:,3])*(target['boxes'][:,2])
        target['iscrowd'] = torch.zeros((num_objs,), dtype=torch.int64)
        return img, target



def get_image_id(filename:str) -> int:
    '''
    Convert a string to a integer.
    Make sure that the images and the `image_id`s are in one-one correspondence.
    There are already `image_id`s in annotations of the COCO dataset,
    in which case this function is unnecessary.
    For creating one's own `get_image_id` function, one can refer to
    https://github.com/google/automl/blob/master/efficientdet/dataset/create_pascal_tfrecord.py#L86
    or refer to the following code (where the filenames are like 'level1_123.jpg')
    # >>> lv, no = os.path.splitext(os.path.basename(filename))[0].split("_")
    # >>> lv = lv.replace("level", "")
    # >>> no = f"{int(no):04d}"
    # >>> return int(lv+no)
    '''
    raise NotImplementedError("Create your own 'get_image_id' function")
    lv, no = os.path.splitext(os.path.basename(filename))[0].split("_")
    lv = lv.replace("level", "")
    no = f"{int(no):04d}"
    return int(lv+no)
'''
"gtboxes": [{"fbox": [72, 202, 163, 503], "tag": "person", 
"hbox": [171, 208, 62, 83], "extra": {"box_id": 0, "occ": 0}, "vbox": [72, 202, 163, 398],
 "head_attr": {"ignore": 0, "occ": 0, "unsure": 0}}, {"fbox": [1
'''

def save_json_lines(content, ID, writer):
    # with open(fpath, 'w') as fid:
    # for db in content:
    #             line = json.dumps(db)+'\n'
    #             fid.write(line)

    gt = {}
    gt["ID"] = 'augv5_'+ID
    gt["gtboxes"]=[]
    tmp = {}
    for box in content:
        if box[4] == 1 and tmp:

            tmp[ "head_attr"] = {"ignore": 0, "occ": 0, "unsure": 0}
            tmp["extra"] ={"box_id": 0, "occ": 0}
            gt["gtboxes"].append(tmp)
            tmp = {}
            tmp["fbox"] = list(box[:4])
            tmp["tag"] = "person"
        elif box[4] == 1:
            tmp["fbox"] = list(box[:4])
        elif box[4] == 2:
            tmp['hbox'] = list(box[:4])
        elif box[4] == 3:
            tmp['vbox'] = list(box[:4])
    if tmp:
        tmp["tag"] = "person"
        tmp["head_attr"] = {"ignore": 0, "occ": 0, "unsure": 0}
        tmp["extra"] ={"box_id": 0, "occ": 0}
        gt["gtboxes"].append(tmp)
    writer.write(json.dumps(gt)+'\n')


if __name__ == "__main__":
    from cfg import Cfg
    import matplotlib.pyplot as plt

    random.seed(2020)
    np.random.seed(2020)
    dataset = CrowdHuman_dataset(Cfg.train_label, Cfg)
    output_path = "/home/weida/datasets/crowdhuman/increasingv6/"
    output__withlable_path = "/home/weida/datasets/crowdhuman/increasing_with_labelv6/"
    output_odgt = "/home/weida/datasets/crowdhuman/annotation_train_augv6.odgt"
    writer = open(output_odgt, "a")

    for i in range(15000):
        out_img, out_bboxes = dataset.__getitem__(i)
        index = dataset.imgs[i].rfind('/')
        cv2.imwrite(os.path.join(output_path, "augv6_"+dataset.imgs[i][index + 1:]), out_img[:, :, [2,1,0]])
        save_json_lines(out_bboxes, dataset.imgs[i][index + 1:-4], writer)
        a = draw_box(out_img.copy(), out_bboxes.astype(np.int32))
        cv2.imwrite(os.path.join(output__withlable_path, "augv6"+dataset.imgs[i][index + 1:]), a[:, :, [2,1,0]])
        # plt.imshow(a.astype(np.int32))
        # plt.show()
