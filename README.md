## 创建一个新的环境 
```
conda create -n your_env python=3.10
```

## 安装chatchat:
```
pip install "langchain-chatchat[xinference]" -U
```

## 删除原先的chatchat 并下载修改过的chatchat
```
cd ~/anaconda3/envs/your_env/lib/python3.10/site-packages
rm -r chatchat
git clone https://github.com/ILIANZBY/Doc_Review
```
## 把拉下来的包改名叫chatchat
