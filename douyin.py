import  requests
import re
import execjs
import time
import datetime
import os
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor



requests.packages.urllib3.disable_warnings()


prodution = 0

base_url = 'https://www.iesdouyin.com/share/user/'
headers = {'User-Agent':'Aweme 7.7.0 rv:77019 (iPhone; iOS 10.3.3; zh_CN) Cronet'}



def _signature(user_id):
    '''
    读取js脚本，获取_signature签名
    :param user_id:  用户id
    :return: signature签名
    '''
    with open('test.js') as f:
        jsstr = f.read()
    cts = execjs.compile(jsstr)
    sign = cts.call('generateSignature',user_id)
    return sign

def download_video(item, path, nickname, flag):
    '''
    下载video
    :param item:  一个视频的数据列表
    :param path:  视频文件父目录
    :param nickname:  用户名
    :param flag:  是否去水印
    :return:
    '''
    global prodution
    title = item.get('desc')
    aweme_id = item.get('aweme_id')
    url = item.get('video').get('play_addr').get('url_list')[0] if flag else \
    item.get('video').get('play_addr').get('url_list')[0]
    filename = path + os.path.sep + title + f'({aweme_id})' + '.mp4'
    if not os.path.exists(filename):
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=5)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    f.write(response.content)
                    print(f'{nickname}: {title}({aweme_id}) 下载成功...')
                    prodution += 1
            else:
                print(f'{nickname}: {title}({aweme_id}) 下载失败...')
        except requests.exceptions.ConnectionError:
            print(f'{nickname}: {title}({aweme_id}) 下载超时...')

def  get_user_data(user_id,dytk,sign, max_cursor=0, n=0):
    '''
    获取数据，如果signature能成功使用， 就递归至下一次请求继续使用，
    :param user_id:
    :param dytk:
    :param sign:
    :param max_cursor:
    :return:
    '''
    url = 'https://www.iesdouyin.com/web/api/v2/aweme/post/'
    headers = {
        'Accept': "application/json",
        'Accept-Encoding': "gzip, deflate, br",
        'Accept-Language': "zh-CN,zh;q=0.9",
        'Connection': "keep-alive",
        'Host': "www.iesdouyin.com",
        'Referer': f"https://www.iesdouyin.com/share/user/{user_id}",
        'Sec-Fetch-Mode': "cors",
        'Sec-Fetch-Site': "same-origin",
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36",
        'X-Requested-With': "XMLHttpRequest",
        'Cache-Control': "no-cache",
    }
    params = {
        "user_id": user_id,
        "sec_uid": "",
        "count": "21",
        "max_cursor": max_cursor,
        "aid": "1128",
        "_signature": sign,
        "dytk": dytk
    }
    count = 0
    while True:
        try:
            response = requests.get(url, headers=headers, params=params, verify=False)
            if response.status_code == 200:
                if len(response.json().get('aweme_list')) > 0:
                    print(response.json())
                    return  response.json(), sign
                # 最后一个ajax请求，  has_more = False
                elif len(response.json().get('aweme_list')) == 0 and not response.json().get('has_more'):
                    return response.json(), sign
                else:
                    count += 1
                #当请求超过30次，没有获取成功到数据时，更换_signature继续请求，直到获取为止
                if count > 30 :
                    # 一次请求密钥替换上限为10次， 如果10次没有获取到数据, 则退出
                    if n == 10:
                        print('_signature密钥出错，请检查生成密钥的js文件')
                        break
                    new_sign = _signature(user_id)
                    n += 1
                    print(f'signature密钥: {sign}已过期，替换为{new_sign}重新请求，替换密钥次数: {n}')
                    #本次函数结束，返回新函数重新请求
                    return get_user_data(user_id, dytk, new_sign, max_cursor, n)
        except Exception as e:
            print(e.args)
            print('请求用户数据发生错误...')
    return None, None

def get_data(user_id, dytk, sign, nickname, flag,path, max_cursor=0):
    '''
    获取ajax页面，执行递归读取和下载视频
    :param user_id:  用户Id
    :param dytk:
    :param sign:  _signature签名
    :param nickname:   用户名
    :param flag:    是否去水印 默认为True
    :param max_cursor:  ajax递归参数
    :return:
    '''
    # 下载视频计数参数
    global prodution

    # 获取数据
    data, sign = get_user_data(user_id, dytk, sign, max_cursor)
    if data is None:
        return
    max_cursor = data.get('max_cursor')
    aweme_list = data.get('aweme_list')
    has_more = data.get('has_more')
    if aweme_list:
        with ThreadPoolExecutor(10) as exector:
            for item in aweme_list:
                exector.submit(download_video,item,path, nickname, flag)
    if has_more:
        get_data(user_id, dytk, sign, nickname, flag,path,max_cursor)
    else:
        print(f'用户: {nickname}  作品下载完成')
        print('成功下载{}个作品'.format(prodution))



def share_user(user_id, flag = True):
    '''
    解析用户基础数据
    :param user_id:  用户id
    :param flag: 是否去水印
    :return:
    '''
    url = base_url + str(user_id)
    response = requests.get(url, headers=headers)
    sign = _signature(user_id) #在这里获取_signature签名，如果没有超时，就继续使用
    if response.status_code == 200 :
        dytk =  re.search("dytk: '(.*?)'",response.text).group(1)
        nickname = re.search('<p class="nickname">(.*?)</p>', response.text).group(1)
        path = 'douyin/' + nickname
        if not os.path.exists(path):
            os.mkdir(path)
        else:
            print(f'该视频目录已存在: {path}, 正在更新作品')
        get_data(user_id, dytk, sign, nickname, flag, path)


if __name__ == '__main__':
    share_user(58479215586)

