import json, os, re, requests, shutil, time, unicodedata, _io
import pandas as pd
from urllib.parse import urljoin
from datetime import datetime
from bs4 import BeautifulSoup
from wcwidth import wcswidth

def count_nonASCII(s: str): #统计一个字符串中占用命令行2个宽度单位的字符个数（Count the number of characters that take up 2 width unit in CMD）
    return sum([unicodedata.east_asian_width(character) in ("F", "W") for character in list(str(s))])

def logPrint(s: str = "", log = None, end: str = "\n"):
    print(s, end = end)
    if isinstance(log, _io.TextIOWrapper):
        log.write(str(s) + end)

def format_df(df: pd.DataFrame, log, width_exceed_ask: bool = True, direct_print: bool = False): #按照每列最长字符串的命令行宽度加上2，再根据每个数据的中文字符数量决定最终格式化输出的字符串宽度（Get the width of the longest string of each column, add it by 2, and substract it by the number of each cell string's Chinese characters to get the final width for each cell to print using `format` function）
    df = df.reset_index(drop = True) #这一步至关重要，因为下面的操作前提是行号是默认的（This step is crucial, for the following operations are based on the dataframe with the default row index）
    maxLens = {}
    maxWidth = shutil.get_terminal_size()[0]
    fields = df.columns.tolist()
    for field in fields:
        maxLens[field] = max(max(map(lambda x: wcswidth(str(x)), df[field])), wcswidth(str(field))) + 2
    if sum(maxLens.values()) + 2 * (len(fields) - 1) > maxWidth: #因为输出的时候，相邻两列之间需要有两个空格分隔，所以在计算总宽度的时候必须算上这些空格的宽度（Because two spaces are used between each pair of columns, the width they take up must be taken into consideration）
        if width_exceed_ask:
            logPrint("单行数据字符串输出宽度超过当前终端窗口宽度！是否继续？（输入任意键继续，否则直接打印该数据框。）\nThe output width of each record string exceeds the current width of the terminal window! Continue? (Input anything to continue, or null to directly print this dataframe.)", log)
            cont = input()
            log.write(cont + "\n")
            if cont == "":
                #print(df)
                result = str(df)
                return (result, maxLens)
        elif direct_print:
            logPrint("单行数据字符串输出宽度超过当前终端窗口宽度！将直接打印该数据框！\nThe output width of each record string exceeds the current width of the terminal window! The program is going to directly print this dataframe!", log)
            result = str(df)
            return (result, maxLens)
        else:
            logPrint("单行数据字符串输出宽度超过当前终端窗口宽度！将继续格式化输出！\nThe output width of each record string exceeds the current width of the terminal window! The program is going on formatted printing!", log)
    result = ""
    for i in range(df.shape[1]):
        field = fields[i]
        tmp = "{0:^{w}}".format(field, w = maxLens[str(field)] - count_nonASCII(str(field))) #算法实现原理：全ASCII字符串可以直接参考前面计算好的宽度进行格式化，因为每个字符占用1个字符宽度。如果字符串中包含一个中文字符，而格式化的宽度不变的话，那么最终格式化得到的结果是整个字符串宽度会多一个单位。所以，当字符串中包含中文字符时，传入format函数的宽度参数应当在原来计算好的宽度的基础上减去中文字符的个数（Algorithm principle: A string that consists of all ASCII characters can be formatted the width based on the width calculated before (`lens`), for each character takes up 1 width unit. If a string consists of a Chinese character and the width parameter in the `format` function stays unchanged, then the final width of the formatted string is actually one unit more than expected. Therefore, when a string contains Chinese characters, the width parameter to be passed into the `format` function should be the previously calculated width subtracted by the number of Chinese characters）
        result += tmp
        #print(tmp, end = "")
        if i != df.shape[1] - 1:
            result += "  "
            #print("  ", end = "")
    result += "\n"
    #print()
    for i in range(df.shape[0]):
        for j in range(df.shape[1]):
            field = fields[j]
            cell = df[field][i]
            tmp = "{0:^{w}}".format(cell, w = maxLens[field] - count_nonASCII(str(cell)))
            result += tmp
            #print(tmp, end = "")
            if j != df.shape[1] - 1:
                result += "  "
                #print("  ", end = "")
        if i != df.shape[0] - 1:
            result += "\n"
        #print() #注意这里的缩进和上一行不同（Note that here the indentation is different from the last line）
    return (result, maxLens)

def getUrl(url: str, log):
    retry = 0
    while True:
        try:
            retry += 1
            source = requests.get(url)
            source.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            if retry > 5:
                break
            if http_err.response.status_code == 404:
                return (source, 404)
        except requests.exceptions.SSLError as ssl_error:
            if retry > 5:
                break
            if "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol" in str(ssl_error):
                logPrint("违反协议导致读取中断！正在尝试第%d次重新获取数据！\nEOF occurred in violation of protocol! Trying to recapture the data with url: %s. Time(s) tried: %d" %(retry, url, retry), log)
            elif 'certificate verify failed' in str(ssl_error):
                logPrint("SSL证书验证失败！正在尝试第%d次重新获取数据！\nSSL certificate verify failed! Trying to recapture the data with url: %s. Time(s) tried: %d" %(retry, url, retry), log)
            elif 'Max retries exceeded with url' in str(ssl_error):
                logPrint("请求数量超过限制！正在尝试第%d次重新获取数据！\nMax retries exceed with url! Trying to recapture the data with url: %s. Time(s) tried: %d" %(retry, url, retry), log)
        except requests.exceptions.ProxyError:
            if retry > 5:
                break
            logPrint("无法连接到代理！正在尝试第%d次重新获取数据！\nCannot connect to proxy! Trying to recapture the data with url: %s. Time(s) tried: %d" %(retry, url, retry), log)
        except requests.exceptions.ChunkedEncodingError:
            if retry > 5:
                break
            logPrint("接收数据块长度不正确导致连接中断！正在尝试第%d次重新获取数据！\nConnection broken: InvalidChunkLength. Trying to recapture the data with url: %s. Time(s) tried: %d" %(retry, url, retry), log)
        except requests.exceptions.ConnectionError:
            if retry > 5:
                break
            logPrint("由于远程服务器端无响应，连接已关闭！正在尝试第%d次重新获取数据！\nRemote end closed connection without response. Trying to recapture the data with url: %s. Time(s) tried: %d" %(retry, url, retry), log)
        except requests.exceptions.ReadTimeout:
            if retry > 5:
                break
            logPrint("读取超时！正在尝试第%d次重新获取数据！\nRead time out! Trying to recapture the data with url: %s. Time(s) tried: %d" %(retry, url, retry), log)
        else:
            return (source, 0)
    if retry > 5:
        return (None, 1)

currentTime = time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())
os.makedirs("离线数据（Offline Data）/Update Logs", exist_ok = True)
log = open(f"离线数据（Offline Data）/Update Logs/{currentTime}.log", "w", encoding = "utf-8")
#控制只输出一遍的提示（Control the hint to be displayed only once）
task_continue_hint = True
ddragon_hint = True
line_re = re.compile('<tr><td class="link"><a href=".*" title=".*">.*</a></td><td class="size">.*</td><td class="date">.*</td></tr>')
while True:
    logPrint("请选择要更新的数据资源，输入空字符串以退出程序：\nPlease select the data resource to update, or submit an empty string to exit the program:\n1\tCommunityDragon\n2\tDataDragon", log)
    resource = input()
    log.write(resource + "\n")
    if resource == "":
        log.write("[The program has exited!]\n")
        log.close()
        break
    elif resource[0] == "1":
        logPrint("请选择要更新的数据资源：\nPlease select the data resources to update:\n☆1\t主要文件（默认）【Major files (by default)】\n2\t自行指定（Specify manually）", log)
        option = input()
        if option != "" and option[0] == "2":
            option = option[0]
        else:
            option = "1"
        logPrint("请选择更新模式：\nPlease select the update mode:\n1\t全局扫描（Global Scan）\n☆2\t按修改时间更新（默认）【Updating According to Modification Time (by default)】", log)
        mode = input()
        log.write(mode + "\n")
        if mode == "" or mode[0] != "1":
            mode = "2"
            logPrint("请选择一种方式指定修改时间：\nPlease select a method of specifying the modification time:\n☆1\t自动获取（默认）【Automatically get (by default)】\n2\t手动输入（Manually input）", log)
            time_get_method = input()
            log.write(time_get_method + "\n")
            if time_get_method == "" or time_get_method[0] != "2":
                time_get_method = "1"
            else:
                time_get_method = "2"
                logPrint('请以“年-月-日 时-分-秒”的格式输入修改时间。示例：2024-05-04 10-26-21。\nPlease input a modification time in the format "%Y-%m-%d %H-%M-%S". Example: 2024-05-04 10-26-21.', log)
                while True:
                    latest_mod_timestamp = input()
                    log.write(latest_mod_timestamp + "\n")
                    if latest_mod_timestamp == "":
                        continue
                    try: #允许输入整型或浮点型时间戳（A timestamp of integer or float type is allowed）
                        latest_mod_timestamp = eval(latest_mod_timestamp)
                        if isinstance(latest_mod_timestamp, (int, float)):
                            break
                    except:
                        try:
                            date_obj = datetime.strptime(latest_mod_timestamp, "%Y-%m-%d %H-%M-%S")
                        except ValueError:
                            logPrint("您的输入格式有误！请重新输入。\nFormat not matched! Please try again.", log)
                        else:
                            latest_mod_timestamp = date_obj.timestamp()
                            break
                latest_mod_date = time.strftime("%Y-%m-%d %H-%M-%S", time.localtime(latest_mod_timestamp))
                logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
                logPrint("指定修改时间（Specified modification time）：%s" %(latest_mod_date), log)
        else:
            mode = "1"
            time_get_method, latest_mod_date = 0, "" #用于后面的文件列表提示动态字符串的初始化。删除后会引发变量未定义的错误（This variable is used for initialization of a subsequent dynamic file list hint string. Deleting it will cause an UnboundLocalError）
        folderRange = ["latest/", "latest/cdragon/arena/", "latest/cdragon/tft/", "latest/plugins/rcp-be-lol-game-data/global/default/v1/champions/", "latest/plugins/rcp-be-lol-game-data/global/default/v1/map-assets/", "latest/plugins/rcp-be-lol-game-data/global/default/v1/", "latest/plugins/rcp-be-lol-game-data/global/zh_cn/v1/champions/", "latest/plugins/rcp-be-lol-game-data/global/zh_cn/v1/map-assets/", "latest/plugins/rcp-be-lol-game-data/global/zh_cn/v1/", "pbe/", "pbe/cdragon/arena/", "pbe/cdragon/tft/", "pbe/plugins/rcp-be-lol-game-data/global/default/v1/champions/", "pbe/plugins/rcp-be-lol-game-data/global/default/v1/map-assets/", "pbe/plugins/rcp-be-lol-game-data/global/default/v1/", "pbe/plugins/rcp-be-lol-game-data/global/zh_cn/v1/champions/", "pbe/plugins/rcp-be-lol-game-data/global/zh_cn/v1/map-assets/", "pbe/plugins/rcp-be-lol-game-data/global/zh_cn/v1/"] #本存储库只收录这些文件夹中的数据资源（This repository only collects data resources under these folders）
        if option == "2":
            logPrint("请选择指定文件夹的输入方式：\nPlease choose an input method to specify the folders:\n☆1\t逐行输入（推荐）【Line by line (recommended)】\n2\t来自文件（From file）", log) #推荐逐行输入，这样指定的文件夹能够记录到日志中（Line-by-line input is recommended, for the specified folders can be recorded into the log in this way）
            input_method = input()
            log.write(input_method + "\n")
            if input_method != "" and input_method[0] == "2":
                logPrint('请输入一个存放CommunityDragon数据库文件夹地址的文本文档的位置：\nPlease input the path of a text file that contains URLs of folders in CommunityDragon database:', log)
                while True:
                    txtfile = input()
                    log.write(txtfile + "\n")
                    if txtfile == "":
                        continue
                    elif os.path.exists(txtfile):
                        break
                    else:
                        logPrint("您输入的地址有误！请重新输入。\nERROR input of the text file path! Please try again.", log)
                with open(txtfile, "r", encoding = "utf-8") as fp:
                    cdragon_folders = list(set(map(lambda x: (x if x.endswith("/") else x[:-len(os.path.basename(x))]).strip("\n").replace("https://raw.communitydragon.org/", "").replace("离线数据（Offline Data）/cdragon/", ""), fp.readlines())))
                if "" in cdragon_folders:
                    cdragon_folders.remove("")
                cdragon_folders.sort()
            else:
                cdragon_folders = []
                logPrint("请逐个输入要更新的CommunityDragon文件夹的地址，输入-1以退出循环：\nPlease input the URLs of CommunityDragon folders to update one by one. Enter -1 to exit the loop:", log)
                while True:
                    cdragon_folder = input()
                    log.write(cdragon_folder + "\n")
                    if cdragon_folder == "":
                        continue
                    elif cdragon_folder == "-1":
                        break
                    else:
                        cdragon_folder = cdragon_folder if cdragon_folder.endswith("/") else cdragon_folder[:-len(os.path.basename(cdragon_folder))]
                        cdragon_folders.append(cdragon_folder.replace("https://raw.communitydragon.org/", "").replace("离线数据（Offline Data）/cdragon/", "")) #请思考，这里如果换成`cdragon_folder.lstrip("https://raw.communitydragon.org/")`，会有什么效果？（Please figure out what will happen if the code is replaced by `cdragon_folder.lstrip("https://raw.communitydragon.org/")`）
                cdragon_folders = list(set(cdragon_folders))
                cdragon_folders.sort()
        else:
            cdragon_folders = folderRange
        web_prefix = "https://raw.communitydragon.org/"
        local_prefix = "离线数据（Offline Data）/cdragon"
        updated_files = []
        added_files = []
        error_folders = []
        error_files = []
        folders_to_delete = [] #统计本地存在而数据库不存在的文件夹（Summarize the folders that exist locally but don't exist in the database）
        files_to_delete = [] #统计本地存在而数据库不存在的文件（Summarize the files that exist locally but don't exist in the database）
        for root, dirs, files in os.walk(local_prefix):
            if not root in folders_to_delete and files != []: #请仔细体会后半个条件的作用（Please try to udnerstand the role of the latter condition）
                folders_to_delete.append(root.replace("\\", "/") + "/")
            if mode == "1": #当更新模式不是全局扫描时，待删除的文件列表不会追加任何文件（When the updating mode isn't [Global Scan], the list that holds the folders to delete won't be appended any files）
                files_to_delete += list(map(lambda x: os.path.join(root, x).replace("\\", "/"), files))
        cnt1 = 0
        for folder in cdragon_folders:
            cnt1 += 1
            cnt2 = 0
            url = urljoin(web_prefix, folder)
            dir = os.path.join(local_prefix, folder).replace("\\", "/")
            logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
            logPrint("[%d/%d]正在检查文件夹（Checking the folder）：%s" %(cnt1, len(cdragon_folders), url), log)
            table = {"file": [], "size": [], "web_date": [], "web_timestamp": [], "local_date": [], "local_timestamp": []}
            source, status = getUrl(url, log)
            if status != 0:
                if status == 1:
                    logPrint("文件夹%s信息获取失败！请等待程序结束后手动比对。\nFolder %s information check failed! Please check manually after the program execution finishes." %(url, url), log)
                    error_folders.append(url)
                    if dir in folders_to_delete:
                        folders_to_delete.remove(dir)
                elif status == 404:
                    logPrint("文件夹%s不存在！\nFolder %s not found!" %(url, url), log)
                continue
            if dir in folders_to_delete:
                folders_to_delete.remove(dir)
            source = source.content.decode()
            source_list = list(map(lambda x: x.strip(), source.split("\n")))
            logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
            optionStr = {"1": {"zh_CN": "页面", "en_US": ""}, "2": {"zh_CN": "指定文件夹涉及的", "en_US": " in specified folders"}}
            modeStr = {"1": {"zh_CN": "", "en_US": "File list"}, "2": {"zh_CN": "新" if time_get_method == "1" else "指定修改时间（%s）后的" %(latest_mod_date), "en_US": "New file list" if time_get_method == "1" else "File list after the specified modification time (%s)" %(latest_mod_date)}}
            logPrint("%s%s文件列表如下：\n%s%s is as follows: " %(optionStr[option]["zh_CN"], modeStr[mode]["zh_CN"], modeStr[mode]["en_US"], optionStr[option]["en_US"]), log)
            for line in source_list:
                matchedLine = line_re.search(line)
                if matchedLine:
                    soup = BeautifulSoup(line, 'lxml')
                    name = soup.find("a")["href"]
                    size = soup.find("td", class_ = "size").text
                    web_date = soup.find("td", class_ = "date").text
                    web_date_obj = datetime.strptime(web_date, "%Y-%b-%d %H:%M")
                    web_timestamp = web_date_obj.timestamp()
                    local_timestamp = os.path.getmtime(os.path.join(local_prefix, folder, name)) if os.path.exists(os.path.join(local_prefix, folder)) and name in os.listdir(os.path.join(local_prefix, folder)) else 0
                    local_date = time.strftime("%Y-%m-%d %H-%M-%S", time.localtime(local_timestamp))
                    if ".json" in name:
                        if folder in folderRange and (not ("cdragon/arena" in folder or "cdragon/tft" in folder) or (name == "en_us.json" or name == "zh_cn.json")) and (mode == "1" or mode == "2" and web_timestamp + time.localtime().tm_gmtoff >= (local_timestamp if time_get_method == "1" else latest_mod_timestamp)):
                            table["file"].append(name)
                            table["size"].append(size)
                            table["web_date"].append(web_date)
                            table["web_timestamp"].append(web_timestamp)
                            table["local_date"].append(local_date)
                            table["local_timestamp"].append(local_timestamp)
            table = pd.DataFrame(table)
            if table.empty:
                logPrint(table, log)
            else:
                logPrint(format_df(table, log, False, True)[0], log)
            os.makedirs(dir, exist_ok = True)
            for i in range(len(table)):
                cnt2 += 1
                name = table["file"][i]
                file_path = os.path.join(local_prefix, folder, name).replace("\\", "/")
                logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
                logPrint("[%d/%d][%d/%d]正在校对文件（Checking file）： %s" %(cnt1, len(cdragon_folders), cnt2, len(table), urljoin(url, name)), log)
                update = added = False
                src, status = getUrl(urljoin(url, name), log)
                if status != 0:
                    if status == 1:
                        logPrint("文件%s比对失败！请等待程序结束后手动比对。\nFile %s check failed! Please check manually after the program execution finishes." %(urljoin(url, name), urljoin(url, name)), log)
                        error_files.append(urljoin(url, name))
                        if file_path in files_to_delete: #比对失败的文件不应删除（Files that fail to be checked shouldn't be deleted）
                            files_to_delete.remove(file_path)
                    elif status == 404:
                        logPrint("文件%s不存在！\nFile %s not found!" %(urljoin(url, name), urljoin(url, name)), log)
                    continue
                if file_path.replace("\\", "/") in files_to_delete:
                    files_to_delete.remove(file_path.replace("\\", "/"))
                try:
                    src = src.json() if name.endswith(".json") else src.text.replace("\r", "")
                except json.decoder.JSONDecodeError as e:
                    if "Unexpected UTF-8 BOM (decode using utf-8-sig)" in str(e): #解决方案来自Stack Overflow（The solution comes from https://stackoverflow.com/questions/71025396/asyncio-and-get-unexpected-utf-8-bom）
                        logPrint("文件编码格式错误！正在尝试改用utf-8-sig编码……\nFile decode error! Trying decoding by utf-8-sig ...", log)
                        src = json.loads(src.text.encode().decode("utf-8-sig"))
                if not name in os.listdir(dir):
                    update = added = True
                else:
                    with open(os.path.join(dir, name), "r", encoding = "utf-8") as fp:
                        dst = json.load(fp) if name.endswith(".json") else fp.read()
                    if src != dst:
                        update = True
                if mode == "1" and update or mode == "2": #当选择全局扫描时，只更新有变化的文档；当选择根据修改时间更新时，如果网页修改时间超前，那么无论文件内容是否发生变化，都重新保存一次，便于后续按照修改时间更新（When the user selects Global Scan, the program updates the changed files. When the user selects Updating according to modification time, if the web modification time of a file succeeds to the local midification time of that, then save the web content to local, no matter whether the web file is same as the local file in terms of content）
                    with open(os.path.join(dir, name), "w", encoding = "utf-8") as fp:
                        if name.endswith(".json"):
                            json.dump(src, fp, indent = 4, ensure_ascii = False)
                        else:
                            fp.write(src)
                if update:
                    if added:
                        logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
                        logPrint("已添加文件（Added file）：%s" %(os.path.join(dir, name)), log)
                        added_files.append(urljoin(url, name))
                    else:
                        logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
                        logPrint("已更新文件（Updated file）：%s" %(os.path.join(dir, name)), log)
                        updated_files.append(urljoin(url, name))
        if updated_files:
            logPrint("已更新以下%d个文件：\nUpdated the following %d file(s):" %(len(updated_files), len(updated_files)), log)
            for file in updated_files:
                logPrint(file, log)
            logPrint("", log)
        if added_files:
            logPrint("已添加以下%d个文件：\nAdded the following %d file(s):" %(len(added_files), len(added_files)), log)
            for file in added_files:
                logPrint(file, log)
            logPrint("", log)
        if error_folders:
            logPrint("以下%d个文件夹比对失败。请重新比对！\nThe following %d folder(s) fail to be checked. Please check manually!" %(len(error_folders), len(error_folders)), log)
            for folder in error_folders:
                logPrint(folder, log)
            logPrint("", log)
        if error_files:
            logPrint("以下%d个文件比对失败。请重新比对！\nThe following %d file(s) fail to be checked. Please check manually!" %(len(error_files), len(error_files)), log)
            for file in error_files:
                logPrint(file, log)
            logPrint("", log)
    elif resource[0] == "2":
        if ddragon_hint:
            hint = '请按以下步骤操作：\nPlease follow these steps:\n1. 访问网址https://developer.riotgames.com/docs/lol#data-dragon\n   Visit the website: https://developer.riotgames.com/docs/lol#data-dragon\n2. 在Latest中找到正式服最新版本数据资源压缩包下载链接。例如：https://ddragon.leagueoflegends.com/cdn/dragontail-15.9.1.tgz\n   Find the link to download the compressed tarball of the latest data resource for live servers. For example: https://ddragon.leagueoflegends.com/cdn/dragontail-15.9.1.tgz\n3. 下载。这需要花费一些时间。\n   Download the file. It may take some time.\n4. 将下载好的tgz文件直接“解压至此”。\n   "Extract here" for the tgz file.\n5. 将解压出来的压缩包再次解压到选定文件夹下与压缩包同名的文件夹。示例：将“dragontail-15.9.1.tar”解压到“D:/360AI浏览器下载/dragontail-15.9.1”文件夹下。\nExtract to "Archive-Name" folder under the selected folder for the extracted tar file. For example, extract "dragontail-15.9.1.tar" into the folder "D:/Downloads/dragontail-15.9.1".\n接下来，请给出数据资源的位置。（按照上例应为“D:/360AI浏览器下载/dragontail-15.9.1/15.9.1/data”。）\nNext, please provide the directory that stores the data resources. (By the above example, the directory should be "D:/Downloads/dragontail-15.9.1/15.9.1/data".)'
            logPrint(hint, log)
            ddragon_hint = False
        else:
            logPrint("请给出数据资源的位置。\nPlease provide the directory that stores the data resources.", log)
        dst_folder = "离线数据（Offline Data）/ddragon"
        while True:
            src_folder = input()
            log.write(src_folder + "\n")
            try:
                if not ("en_US" in os.listdir(src_folder) and "zh_CN" in os.listdir(src_folder)):
                    logPrint("您输入的地址有误！请重新输入！\nERROR input of data resource directory! Please try again!", log)
                else:
                    break
            except FileNotFoundError:
                logPrint("您输入的地址有误！请重新输入！\nERROR input of data resource directory! Please try again!", log)
        added_files = []
        updated_files = []
        error_files = []
        cnt1 = 0
        for root, dirs, files in os.walk(src_folder):
            for file in files:
                update = added = False
                if file.endswith(".json"):
                    src_path = os.path.join(root, file).replace("\\", "/")
                    relative_path = os.path.relpath(root, src_folder).replace("\\", "/")
                    dst_path = os.path.join(dst_folder, relative_path, file).replace("\\", "/")
                    if "en_US" in relative_path or "zh_CN" in relative_path:
                        cnt1 += 1
                        os.makedirs(os.path.dirname(dst_path), exist_ok = True)
                        logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
                        logPrint("[%d]正在校对文件（Checking file）： %s" %(cnt1, src_path), log)
                        with open(src_path, "r", encoding = "utf-8") as fp:
                            src = json.load(fp)
                        if not file in os.listdir(os.path.join(dst_folder, relative_path)):
                            update = added = True
                        else:
                            with open(dst_path, "r", encoding = "utf-8") as fp:
                                dst = json.load(fp)
                            if src != dst:
                                update = True
                        if update:
                            with open(dst_path, "w", encoding = "utf-8") as fp:
                                json.dump(src, fp, indent = 4, ensure_ascii = False)
                            if added:
                                logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
                                logPrint("[%d]已添加文件（Added file）：%s" %(cnt1, dst_path), log)
                                added_files.append(src_path)
                            else:
                                logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
                                logPrint("[%d]已更新文件（Updated file）：%s" %(cnt1, dst_path), log)
                                updated_files.append(src_path)
        cnt1 += 1
        version_url = "https://ddragon.leagueoflegends.com/api/versions.json"
        logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
        logPrint("[%d]正在校对文件（Checking file）： %s" %(cnt1, version_url), log)
        update = added = False
        src, status = getUrl(version_url, log)
        if status != 0:
            if status == 1:
                logPrint("文件%s比对失败！请等待程序结束后手动比对。\nFile %s check failed! Please check manually after the program execution finishes." %(version_url, version_url), log)
            elif status == 404:
                logPrint("文件%s不存在！请等待程序结束后手动比对。\nFile %s not found! Please check manually after the program execution finishes." %(version_url, version_url), log)
            error_files.append(version_url)
            continue
        src = src.json()
        if not "versions.json" in os.listdir("离线数据（Offline Data）"):
            update = added = True
        else:
            with open("离线数据（Offline Data）/versions.json", "r", encoding = "utf-8") as fp:
                dst = json.load(fp)
            if src != dst:
                update = True
        if update:
            with open("离线数据（Offline Data）/versions.json", "w", encoding = "utf-8") as fp:
                json.dump(src, fp, indent = 4, ensure_ascii = False)
            if added:
                logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
                logPrint("[%d]已添加文件（Added file）：离线数据（Offline Data）/versions.json" %cnt1, log)
                added_files.append("离线数据（Offline Data）/versions.json")
            else:
                logPrint("[%s]" %(time.strftime("%Y-%m-%d %H-%M-%S", time.localtime())), log, end = "")
                logPrint("[%d]已更新文件（Updated file）：离线数据（Offline Data）/versions.json" %cnt1, log)
                updated_files.append("离线数据（Offline Data）/versions.json")
    else:
        logPrint("您的输入有误！请重新输入。\nERROR input! Please try again.", log)
print("比对完成！请按回车键退出。\nCheck finished! Press Enter to exit.")
input()