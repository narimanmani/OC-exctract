import os
from pprint import pprint

import pytz
import requests
import pandas as pd
import numpy as np
import time
import csv, json
import seaborn as sns
import matplotlib.pyplot as plt
import datetime
from dateutil.relativedelta import relativedelta
from collections import Counter
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import *
from scipy.spatial.distance import cdist
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN
from matplotlib import pyplot as plt
from sklearn import preprocessing
import glob

github_personal_token_input="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"
personal_token = github_personal_token_input
token = os.getenv('GITHUB_TOKEN', personal_token)
headers = {'Authorization': f'token {token}'}

desired_width=640
pd.set_option('display.width', desired_width)
np.set_printoptions(linewidth=desired_width)
pd.set_option('display.max_columns',60)

df_selected = pd.read_csv('./OldData/filtered_lang_perc.csv')
listofprojects38 = df_selected.loc[:, 'github_url'].values.tolist()
df_all_commits = pd.read_csv('./OldData/all_commits_NEW_noPatch_service_ex_lang_onlyservice_id_sum.csv')

#for i in listofprojects38:
#    print(i)

def getCommitTablebyProject(projectfullname, updateissuetablename):
    theCommitQuery = f"https://api.github.com/repos/{projectfullname}/commits"
    theProjectQuery = f"https://api.github.com/repos/{projectfullname}"
    p_search = requests.get(theProjectQuery, headers=headers)
    project_info = p_search.json()
    project_id = project_info['id']
    params = {'per_page': 100}
    page = 1
    #projectissuedataitems = []
    commit_features = ['project_id', 'commit_sha', 'author_email', 'author_date']
    with open(updateissuetablename, 'a', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(commit_features)
    while 1 == 1:
        params['page'] = page
        print(page)
        print(projectfullname + ' ' + 'page ' + str(page))
        theResult = requests.get(theCommitQuery, headers=headers, params=params)
        theItemListPerPage = theResult.json()
        if len(theItemListPerPage) == 0:
            break
        else:
            print(len(theItemListPerPage))
            for item in theItemListPerPage:
                commititem = {}
                commititem['project_id'] = project_id
                commititem['commit_sha'] = item['sha']
                try:
                    commititem['author_email'] = item['commit']['author']['email']
                except:
                    commititem['author_email'] = np.NaN
                commititem['author_date'] = item['commit']['author']['date']
                #try:
                #    commititem['message'] = item['commit']['message']
                #except:
                #    commititem['message'] = np.NaN

                with open(updateissuetablename, 'a', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile, delimiter=',')
                    writer.writerow([commititem[x] for x in commit_features])
                #projectissuedataitems.append(commititem)
            page = page + 1

def furtherCrawlCommits(commitsdf, projectfullname, newupdateissuetablename):
    commitsshalist = commitsdf.loc[:, 'commit_sha'].values.tolist()
    commit_features = ['project', 'commit_sha', 'author_email', 'author_date', 'file_sha', 'filename', 'status', 'additions', 'deletions', 'patch', 'previous_filename']
    with open(newupdateissuetablename, 'a', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(commit_features)
    for sha in commitsshalist:
        print(sha)
        theCommitQuery = f"https://api.github.com/repos/{projectfullname}/commits/{sha}"
        #theProjectQuery = f"https://api.github.com/repos/{projectfullname}"
        commit_search = requests.get(theCommitQuery, headers=headers)
        commit_info = commit_search.json()
        #project_id = project_info['id']
        #params = {'per_page': 100}
        #page = 1
        print(commit_info)
        commititem = {}
        commititem['project'] = projectfullname
        commititem['commit_sha'] = sha
        try:
            commititem['author_email'] = commit_info['commit']['author']['email']
        except:
            commititem['author_email'] = np.NaN
        try:
            commititem['author_date'] = commit_info['commit']['author']['date']
        except:
            commititem['author_date'] = np.NaN
        thefiles = commit_info['files']
        for file in thefiles:
            commititemFile = commititem.copy()
            commititemFile['file_sha'] = file['sha']
            commititemFile['filename'] = file['filename']
            commititemFile['status'] = file['status']
            commititemFile['additions'] = file['additions']
            commititemFile['deletions'] = file['deletions']
            #commititemFile['contents_url'] = file['contents_url']
            try:
                commititemFile['patch'] = file['patch']
            except:
                commititemFile['patch'] = np.NaN
            try:
                commititemFile['previous_filename'] = file['previous_filename']
            except:
                commititemFile['previous_filename'] = np.NaN
            with open(newupdateissuetablename, 'a', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                writer.writerow([commititemFile[x] for x in commit_features])

def furtherCrawlCommitsContinuefromBreak(commitsdf, projectfullname, newupdateissuetablename, startpoint):
    commitsshalist = commitsdf.loc[:, 'commit_sha'].values.tolist()
    commit_features = ['project', 'commit_sha', 'author_email', 'author_date', 'file_sha', 'filename', 'status',
                       'additions', 'deletions', 'patch', 'previous_filename']
    #existing_df = pd.read_csv(newupdateissuetablename) #4533
    for sha in commitsshalist[startpoint:]:
        print(sha)
        theCommitQuery = f"https://api.github.com/repos/{projectfullname}/commits/{sha}"
        #theProjectQuery = f"https://api.github.com/repos/{projectfullname}"
        commit_search = requests.get(theCommitQuery, headers=headers)
        commit_info = commit_search.json()
        #project_id = project_info['id']
        #params = {'per_page': 100}
        #page = 1
        print(commit_info)
        commititem = {}
        commititem['project'] = projectfullname
        commititem['commit_sha'] = sha
        try:
            commititem['author_email'] = commit_info['commit']['author']['email']
        except:
            commititem['author_email'] = np.NaN
        try:
            commititem['author_date'] = commit_info['commit']['author']['date']
        except:
            commititem['author_date'] = np.NaN
        thefiles = commit_info['files']
        for file in thefiles:
            commititemFile = commititem.copy()
            commititemFile['file_sha'] = file['sha']
            commititemFile['filename'] = file['filename']
            commititemFile['status'] = file['status']
            commititemFile['additions'] = file['additions']
            commititemFile['deletions'] = file['deletions']
            #commititemFile['contents_url'] = file['contents_url']
            try:
                commititemFile['patch'] = file['patch']
            except:
                commititemFile['patch'] = np.NaN
            try:
                commititemFile['previous_filename'] = file['previous_filename']
            except:
                commititemFile['previous_filename'] = np.NaN
            with open(newupdateissuetablename, 'a', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                writer.writerow([commititemFile[x] for x in commit_features])

#projecturl = "https://github.com/CDLUC3/merritt-docker"
#projectfullname = '/'.join(projecturl.split("/")[-2:])
#print(projectfullname)
#projectcommitCSV = 'EsoccExt/'+'_'.join(projectfullname.split('/'))+'.csv'
#projectcommitCSVfull = '_full.'.join(projectcommitCSV.split('.'))

#getCommitTablebyProject(projectfullname, projectcommitCSV)
#df = pd.read_csv('./'+projectcommitCSV)
#furtherCrawlCommits(df, projectfullname, projectcommitCSVfull)
#furtherCrawlCommitsContinuefromBreak(df, projectfullname, projectcommitCSVfull, 3128)

#df = pd.read_csv('filtered_all_commits.csv')
#print(df.head(20))

#all_commit_files = glob.glob("EsoccExt/*_full.csv")
#df_all = pd.concat((pd.read_csv(f) for f in all_commit_files), ignore_index=True)
#print(df_all.head())
#print(df_all.shape)
#df_all.drop(columns='patch', inplace=True)
#df_all.to_csv('EsoccExt/all_commit_new_lite.csv', index=False)

#df_old = pd.read_csv('filtered_all_commits.csv')
#df_old = df_old.loc[:, ['github_url', 'service_name']]
#df_old.dropna(subset = ["service_name"], inplace=True)
#df_old.drop_duplicates(inplace=True)
#df_g = df_old.groupby('github_url').count().reset_index()




df_all = pd.read_csv('./EsoccExt/all_commit_new_lite_service.csv')
df_service = pd.read_csv('./EsoccExt/service_check3.csv')


def dropfrontback(thetext):
    return thetext[1:]
def urltoproject(theurl):
    return '/'.join(theurl.split('/')[-2:])

#df_service['project'] = df_service['github_url'].apply(urltoproject)
#df_service = df_service.loc[:, ['project', 'service_name']]
#df_service.to_csv('EsoccExt/service_check3.csv', index=False)


#filenamelist = df_all['filename'].values.tolist()
#servicelist = df_service['service_name'].values.tolist()
#print(filenamelist[0])

#with open('EsoccExt/servicelist.txt', 'a', encoding='utf-8') as txtfile:
#    for i in range(len(filenamelist)):
#        print(i)
#        temp = [x for x in servicelist if x in filenamelist[i]]
#        if temp:
#            txtfile.write(temp[0] + '\n')
#        else:
#            txtfile.write('null' + '\n')
#print(filenamelist[1])
#print(servicelist)
#print([x for x in servicelist if x in filenamelist[1]])


#with open('EsoccExt/servicelist.txt', 'r', encoding='utf-8') as txtfile:
#    servicelist = [x.strip('\n') for x in txtfile.readlines()]
#df_all['service'] = servicelist
#df_all.to_csv('EsoccExt/all_commit_new_lite_service.csv', index=False)

#all_commit_files = glob.glob("EsoccExt/*_full_service.csv")
#for item in all_commit_files:
#    df_temp = pd.read_csv(item)
#    print(df_temp.head())
#    theproject = df_temp.loc[:,'project'].values.tolist()[0]
#    servicelist = df_service.loc[df_service['project'] == theproject, 'service_name'].values.tolist()
#    print(servicelist)
#    thisfilelist = df_temp['filename'].values.tolist()
#    theservicesforeacfiles = []
#    for i in range(len(thisfilelist)):
#        print(i)
#        temp = [x for x in servicelist if x in thisfilelist[i]]
#        if temp:
#            theservicesforeacfiles.append(temp[0])
#        else:
#            theservicesforeacfiles.append('null')
#    df_temp['service'] = theservicesforeacfiles
#    df_temp.to_csv('_service.'.join(item.split('.')), index=False)
#df_all = pd.concat((pd.read_csv(f) for f in all_commit_files), ignore_index=True)
#print(df_all.head())
#print(df_all.shape)
#df_all.drop(columns='patch', inplace=True)
#df_all.to_csv('EsoccExt/all_commit_new_lite_service.csv', index=False)

#df_all = pd.concat((pd.read_csv(f) for f in all_commit_files), ignore_index=True)
#print(df_all.head())




def getServiceContributorDict(theproject, thecommitdf, thetime):
    ms_commit_df = thecommitdf.loc[(thecommitdf['author_date']<=thetime) & (thecommitdf['project']==theproject)]
    ms_commit_df.dropna(subset=['service'], inplace=True)
    #def getservice(project):
    #    return project.split('/')[-1]
    #ms_commit_df['service'] = ms_commit_df['project'].apply(getservice)
    #currentServices = [x.split('/')[-1] for x in list(set(ms_commit_df.loc[:, 'project'].values.tolist()))]
    currentServices = list(set(ms_commit_df.loc[:, 'service'].values.tolist()))
    #print(currentServices)
    #print(thecommitdf.head())
    def getUsernamefromEmail(theemail):
        return theemail.split('@')[0]
    print(currentServices)
    for service in currentServices:
        theDict = {}
        theselected = ms_commit_df.loc[ms_commit_df['service']==service, ['author_email','filename','additions', 'deletions']]
        theselected['author_email'] = theselected['author_email'].apply(getUsernamefromEmail)
        theselected_gb = theselected.groupby('author_email').sum()
        theselected_gb.reset_index(inplace=True)
        theselected_gb['sum'] = theselected_gb['additions'] + theselected_gb['deletions']
        contributorDict = theselected_gb.set_index('author_email').to_dict()['sum']
        contributorDict = sorted(contributorDict.items(), key=lambda item: item[1], reverse=True)
        tempsum = sum([x[1] for x in contributorDict])
        contributorDict = [(x[0], round(x[1]/tempsum, 4)) for x in contributorDict]
        print(contributorDict)
        #theDict[service] = contributorDict
        theDict['author'] = [x[0] for x in contributorDict]
        theDict['per'] = [x[1] for x in contributorDict]
        thedf = pd.DataFrame.from_dict(theDict)
        #thedf.to_csv('$'.join(theproject.split('/'))+'€'+'$'.join(service.split('/'))+'.csv', index=False)
    return theDict

def getSwitchingForContributorBetweenMS(theproject, thecommitdf, thetime, theauthor, m1, m2):
    ms_commit_df = thecommitdf.loc[(thecommitdf['author_date']<=thetime) & (thecommitdf['project']==theproject)]
    def getUsernamefromEmail(theemail):
        return theemail.split('@')[0]
    ms_commit_df['author'] = ms_commit_df['author_email'].apply(getUsernamefromEmail)
    ms_commit_df.dropna(subset=['service'], inplace=True)

    theauthor_ms_df = ms_commit_df.loc[ms_commit_df['author']==theauthor, :]
    #theauthor_ms_df = theauthor_df.loc[theauthor_df['filename'].str.contains('src/Services/'), ['commit_sha','author_email', 'author_date', 'filename', 'additions', 'deletions']]
    #def getService(theservicefilename):
    #    return theservicefilename.split('/')[-1]
    #theauthor_ms_df['service'] = theauthor_ms_df['project'].apply(getService)
    theauthor_ms_df.sort_values(by=['author_date'], inplace=True)
    theauthor_ms_df['sum'] = theauthor_ms_df['additions'] + theauthor_ms_df['deletions']
    theauthor_ms_df = theauthor_ms_df.loc[:, ['commit_sha','author_date','service','sum']]
    theauthor_ms_df_gb = theauthor_ms_df.groupby(['author_date', 'commit_sha', 'service']).sum()
    theauthor_ms_df_gb.reset_index(inplace=True)
    theauthor_ms_df_gb = theauthor_ms_df_gb.loc[(theauthor_ms_df_gb['service']==m1)|(theauthor_ms_df_gb['service']==m2), :]
    #def splitServices(thestring):
    #    return list(set(thestring.split('-')[:-1]))
    #theauthor_ms_df_gb['service'] = theauthor_ms_df_gb['service'].apply(splitServices)
    #print(theauthor_ms_df_gb.head(40))
    serviceseq = theauthor_ms_df_gb.loc[:, 'service'].values.tolist()
    switchcount = 0
    for i in range(len(serviceseq)-1):
        if serviceseq[i] == serviceseq[i+1]:
            continue
        else:
            switchcount = switchcount + 1
    commitcount = len(serviceseq)
    return switchcount/((commitcount-1)*2)

def getCoupling(theproject, thecommitdf, thetimefrom, thetimeto, m1, m2):
    ms_commit_df = thecommitdf.loc[(thecommitdf['author_date']<thetimeto) &(thecommitdf['author_date']>=thetimefrom) & (thecommitdf['project']==theproject)]
    def getUsernamefromEmail(theemail):
        return theemail.split('@')[0]
    ms_commit_df['author'] = ms_commit_df['author_email'].apply(getUsernamefromEmail)
    ms_commit_df.dropna(subset=['service'], inplace=True)
    #def getService(theservicefilename):
    #    return theservicefilename.split('/')[-1]
    #ms_commit_df['service'] = ms_commit_df['project'].apply(getService)
    ms_commit_df.sort_values(by=['author_date'], inplace=True)
    ms_commit_df['sum'] = ms_commit_df['additions'] + ms_commit_df['deletions']
    ms_commit_df = ms_commit_df.loc[:, ['commit_sha', 'author', 'author_date', 'service', 'sum']]
    ms_commit_df_gb = ms_commit_df.groupby(['author_date', 'commit_sha', 'author', 'service']).sum()
    ms_commit_df_gb.reset_index(inplace=True)
    ms_commit_df_gb = ms_commit_df_gb.loc[(ms_commit_df_gb['service']==m1)|(ms_commit_df_gb['service']==m2), :]
    authorlist1 = list(set(ms_commit_df_gb.loc[ms_commit_df_gb['service']==m1, 'author'].values.tolist()))
    authorlist2 = list(set(ms_commit_df_gb.loc[ms_commit_df_gb['service']==m2, 'author'].values.tolist()))
    coupleauthors = [x for x in authorlist1 if x in authorlist2]
    authorcouplinglist = []
    for author in coupleauthors:
        ms_commit_df_gb_author = ms_commit_df_gb.loc[ms_commit_df_gb['author']==author, :]
        serviceseq = ms_commit_df_gb_author.loc[:, 'service'].values.tolist()
        switchcount = 0
        for i in range(len(serviceseq) - 1):
            if serviceseq[i] == serviceseq[i + 1]:
                continue
            else:
                switchcount = switchcount + 1
        commitcount = len(serviceseq)
        weight = switchcount / ((commitcount - 1) * 2)
        sumcontribution_m1 = sum(ms_commit_df_gb_author.loc[ms_commit_df_gb_author['service'] == m1, 'sum'].values.tolist())
        sumcontribution_m2 = sum(ms_commit_df_gb_author.loc[ms_commit_df_gb_author['service'] == m2, 'sum'].values.tolist())
        authorcouplinglist.append(2*sumcontribution_m1*sumcontribution_m2/(sumcontribution_m1+sumcontribution_m2)*weight)
    return sum(authorcouplinglist)

def makeNodeEdgeCSV(theproject, thecommitdf, thetime):
    newcsv = f"{theproject.split('/')[0]}_{theproject.split('/')[1]}_edgecsv_{thetime}.csv"
    features = ['Source','Target','Weight']
    ms_commit_df = thecommitdf.loc[(thecommitdf['author_date']<=thetime) & (thecommitdf['project']==theproject)]
    ms_commit_df.dropna(subset=['service'], inplace=True)
    servicelist = list(set(ms_commit_df.loc[:, 'service'].values.tolist()))

    #servicelist = list(set([x.split('/')[-1] for x in ms_commit_df.loc[:, 'project'].values.tolist()]))
    print(servicelist)
    with open(newcsv, 'a', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(features)
    for i in range(len(servicelist)):
        for j in range(i+1, len(servicelist)):
            print([i,j])
            with open(newcsv, 'a', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                writer.writerow([servicelist[i], servicelist[j], getCoupling(theproject,thecommitdf, thetime, servicelist[i], servicelist[j])])

def makeHeatmapdataset(theproject, thecommitdf, thetime):
    newcsv = f"{theproject.split('/')[0]}_{theproject.split('/')[1]}_heatmap_{thetime}.csv"
    ms_commit_df = thecommitdf.loc[(thecommitdf['author_date']<=thetime) & (thecommitdf['project']==theproject)]
    #servicelist = list(set([x.split('/')[-1] for x in ms_commit_df.loc[:, 'project'].values.tolist()]))
    ms_commit_df.dropna(subset=['service'], inplace=True)
    servicelist = list(set(ms_commit_df.loc[:, 'service'].values.tolist()))
    servicelist = sorted(servicelist)
    features = [' '] + servicelist
    with open(newcsv, 'a', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(features)
    for i in range(len(servicelist)):
        row = [servicelist[i]]
        for j in range(len(servicelist)):
            if i == j:
                row.append(0)
            else:
                row.append(getCoupling(theproject, thecommitdf, thetime, servicelist[i], servicelist[j]))
        with open(newcsv, 'a', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(row)

def getCoupling_BetweenDate(theproject, thecommitdf, thetimefrom, thetimeto, m1, m2):
    ms_commit_df = thecommitdf.loc[(thecommitdf['author_date'] <= thetimeto) & (thecommitdf['author_date'] > thetimefrom) & (thecommitdf['project']==theproject)]
    def getUsernamefromEmail(theemail):
        return str(theemail).split('@')[0]
    ms_commit_df['author'] = ms_commit_df['author_email'].apply(getUsernamefromEmail)
    #def getService(theservicefilename):
    #    return theservicefilename.split('/')[-1]
    #ms_commit_df['service'] = ms_commit_df['project'].apply(getService)
    ms_commit_df.dropna(subset=['service'], inplace=True)
    ms_commit_df.sort_values(by=['author_date'], inplace=True)
    ms_commit_df['sum'] = ms_commit_df['additions'] + ms_commit_df['deletions']
    ms_commit_df = ms_commit_df.loc[:, ['commit_sha', 'author', 'author_date', 'service', 'sum']]
    ms_commit_df_gb = ms_commit_df.groupby(['author_date', 'commit_sha', 'author', 'service']).sum()
    ms_commit_df_gb.reset_index(inplace=True)
    ms_commit_df_gb = ms_commit_df_gb.loc[(ms_commit_df_gb['service']==m1)|(ms_commit_df_gb['service']==m2), :]
    authorlist1 = list(set(ms_commit_df_gb.loc[ms_commit_df_gb['service']==m1, 'author'].values.tolist()))
    authorlist2 = list(set(ms_commit_df_gb.loc[ms_commit_df_gb['service']==m2, 'author'].values.tolist()))
    coupleauthors = [x for x in authorlist1 if x in authorlist2]
    authorcouplinglist = []
    for author in coupleauthors:
        ms_commit_df_gb_author = ms_commit_df_gb.loc[ms_commit_df_gb['author']==author, :]
        serviceseq = ms_commit_df_gb_author.loc[:, 'service'].values.tolist()
        switchcount = 0
        for i in range(len(serviceseq) - 1):
            if serviceseq[i] == serviceseq[i + 1]:
                continue
            else:
                switchcount = switchcount + 1
        commitcount = len(serviceseq)
        weight = switchcount / ((commitcount - 1) * 2)
        sumcontribution_m1 = sum(ms_commit_df_gb_author.loc[ms_commit_df_gb_author['service'] == m1, 'sum'].values.tolist())
        sumcontribution_m2 = sum(ms_commit_df_gb_author.loc[ms_commit_df_gb_author['service'] == m2, 'sum'].values.tolist())
        try:
            authorcouplinglist.append(2*sumcontribution_m1*sumcontribution_m2/(sumcontribution_m1+sumcontribution_m2)*weight)
        except:
            authorcouplinglist.append(0)
    return sum(authorcouplinglist)


def makeHeatmapdatasetBetweenDate(theproject, thecommitdf, thetimefrom, thetimeto):
    newcsv = f"{theproject.split('/')[0]}_{theproject.split('/')[1]}_heatmap_{thetimefrom}_{thetimeto}.csv"
    ms_commit_df = thecommitdf.loc[(thecommitdf['author_date'] <= thetimeto) & (thecommitdf['author_date'] > thetimefrom) & (thecommitdf['project']==theproject)]
    #servicelist = list(set([x.split('/')[-1] for x in ms_commit_df.loc[:, 'project'].values.tolist()]))
    ms_commit_df.dropna(subset=['service'], inplace=True)
    servicelist = list(set(ms_commit_df.loc[:, 'service'].values.tolist()))
    servicelist = sorted(servicelist)
    features = [' '] + servicelist
    with open(newcsv, 'a', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(features)
    for i in range(len(servicelist)):
        row = [servicelist[i]]
        for j in range(len(servicelist)):
            if i == j:
                row.append(0)
            else:
                row.append(getCoupling_BetweenDate(theproject, thecommitdf, thetimefrom, thetimeto, servicelist[i], servicelist[j]))
        with open(newcsv, 'a', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(row)

def makeAllProjectMSPerDeveloperSortedby(theselecteddf):
    #projectlist = list(set(theselecteddf.loc[:, 'github_url'].values.tolist()))
    df_gb_dn = theselecteddf.groupby(['project'])['author_email'].nunique()
    df_gb_dn = df_gb_dn.to_frame()
    df_gb_dn.reset_index(inplace=True)
    df_gb_dn.sort_values(by=['author_email'], inplace=True, ascending=False)
    sortedprojectlist = df_gb_dn.loc[:, 'project'].values.tolist()
    sortedprojectnumbers = df_gb_dn.loc[:, 'author_email'].values.tolist()
    #print(df_gb_dn)
    df_gb = theselecteddf.groupby(['project', 'author_email'])['service'].nunique()
    df_gb = df_gb.to_frame()
    df_gb.reset_index(inplace=True)
    theData = []
    for project in sortedprojectlist:
        theData.append(df_gb.loc[df_gb['project'] == project, 'service'].values)
    # print(theData)
    my_dpi = 96
    plt.figure(figsize=(1280 / my_dpi, 720 / my_dpi), dpi=my_dpi)
    fig, ax1 = plt.subplots()
    #fig.canvas.set_window_title('A Boxplot Example')
    plt.subplots_adjust(left=0.075, right=0.95, top=0.9, bottom=0.25)
    xtickNames = plt.setp(ax1, xticklabels=sortedprojectnumbers)
    plt.setp(xtickNames, rotation=90, fontsize=8)
    #fig = plt.figure(figsize=(10, 7))
    # Creating axes instance
    #fig7, ax7 = plt.subplots()
    # Creating plot
    ax1.boxplot(theData, showfliers=False)
    plt.xlabel('Projects (The Number of Developers for each Project)')
    plt.ylabel('Microservices per Contributor')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    plt.savefig('testing.png', bbox_inches='tight')
    plt.show()

def makeAllProjectMSPerDeveloperSortedbyMS(theselecteddf):
    #projectlist = list(set(theselecteddf.loc[:, 'github_url'].values.tolist()))
    df_gb_dn = theselecteddf.groupby(['project'])['service'].nunique()
    df_gb_dn = df_gb_dn.to_frame()
    df_gb_dn.reset_index(inplace=True)
    df_gb_dn.sort_values(by=['service'], inplace=True, ascending=False)
    sortedprojectlist = df_gb_dn.loc[:, 'project'].values.tolist()
    sortedprojectnumbers = df_gb_dn.loc[:, 'service'].values.tolist()
    print(df_gb_dn)
    df_gb = theselecteddf.groupby(['project', 'author_email'])['service'].nunique()
    df_gb = df_gb.to_frame()
    df_gb.reset_index(inplace=True)
    theData = []
    for project in sortedprojectlist:
        theData.append(df_gb.loc[df_gb['project'] == project, 'service'].values)
    # print(theData)
    my_dpi = 96
    plt.figure(figsize=(1280 / my_dpi, 720 / my_dpi), dpi=my_dpi)
    fig, ax1 = plt.subplots()
    #fig.canvas.set_window_title('A Boxplot Example')
    plt.subplots_adjust(left=0.075, right=0.95, top=0.9, bottom=0.25)
    xtickNames = plt.setp(ax1, xticklabels=sortedprojectnumbers)
    plt.setp(xtickNames, rotation=90, fontsize=8)
    #fig = plt.figure(figsize=(10, 7))
    # Creating axes instance
    #fig7, ax7 = plt.subplots()
    # Creating plot
    bp = ax1.boxplot(theData, showfliers=True)
    plt.xlabel('Projects (The Number of Microservices for each Project)')
    plt.ylabel('Microservices per Contributor')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    plt.savefig('testingMSwith154withOutliners.png', bbox_inches='tight')

    #bp.spines['bottom'].set_visible(False)
    #bp.spines['left'].set_visible(False)
    #print([item.get_ydata() for item in bp['whiskers']])
    #plt.savefig('sortedbyMSnumbers2.png', bbox_inches='tight')
    plt.show()

#print(getServiceContributorDict('emissary-ingress/emissary', df_all, '2024-01-01'))
#print(df_all.head())

#for project in listofprojects38[11:]:
#    makeHeatmapdatasetBetweenDate(project.split('github.com/')[-1], df_all, '2018-01-01', '2023-12-31')

def checkFileType(new_file_path):
    if '/' in str(new_file_path).split('.')[-1]:
        return np.NaN
    else:
        return '.'+str(new_file_path).split('.')[-1]

def ext2Lang(theextension):
    dfext = pd.read_csv('Extensions2LanguageType.csv')
    exlist = dfext.Extension.tolist()
    #labglist = dfext.Language.tolist()
    if theextension in exlist:
        return dfext.loc[dfext['Extension']==theextension, 'Language'].values.tolist()[0]
    else:
        return 'Others'
    #print(sorted(dict(Counter(exlist)).items(), key = lambda x: x[1], reverse=True))

#df_lang = pd.read_csv('filtered_all_commits_ex_lang4.csv')
#print(df_lang.head())
#all_commit_files = glob.glob("EsoccExt/*_full_service.csv")
#df_all = pd.concat((pd.read_csv(f) for f in all_commit_files), ignore_index=True)
#df_all.drop(['patch'], axis=1, inplace=True)
#df_all.to_csv('all_commits_NEW_noPatch_service.csv', index=False)

#df['extension'] = df['filename'].apply(checkFileType)
#df.to_csv('all_commits_NEW_noPatch_service_ex.csv', index=False)
#df['lang'] = df['extension'].apply(ext2Lang)
#df.to_csv('all_commits_NEW_noPatch_service_ex_lang.csv', index=False)

#df['sum'] = df['additions'] + df['deletions']
#df_gb = df.groupby(['author_email', 'lang'])['sum'].sum().unstack()
#df_gb = df_gb.fillna(0)
#df_gb.reset_index(inplace=True)
#print(df_gb.head(10))
#df_gb.to_csv('author_lang_sum_NEW.csv', index=False)
#df_dropna = df.dropna(subset=['service'])
#df_dropna.to_csv('all_commits_NEW_noPatch_service_ex_lang_onlyservice.csv', index=False)

def get6factorScoresforEach(thedf, authorid):
    #df = pd.read_csv('devkmeans5NEW.csv')
    theseries = thedf.drop('authorid', axis=1)
    #theseries = theseries.drop(['cluster'], 1)
    x = theseries.values  # returns a numpy array
    min_max_scaler = preprocessing.MinMaxScaler()
    x_scaled = min_max_scaler.fit_transform(x)
    normalized_df = pd.DataFrame(x_scaled)
    # normalized_df = (theseries - theseries.min()) / (theseries.max() - theseries.min())
    normalized_df.columns = theseries.columns
    normalized_df['authorid'] = thedf['authorid']
    thenormalizedseries = normalized_df.loc[normalized_df['authorid']==authorid, :]
    thedict = thenormalizedseries.to_dict('records')[0]
    f = {}
    newF = {}
    #f['f1'] = [('Thrift', 0.9974), ('C', 0.9958), ('Lua', 0.9638), ('CMake', 0.9019), ('Others', 0.7362),('C++', 0.4743)]
    #f['f8'] = [('TypeScript', 0.9809)]
    #f['f9'] = [('C#', 0.911)]
    #f['f10'] = [('Batchfile', 0.9898)]
    #f['f12'] = [('C++', 0.8362)]
    #f['f2'] = [('Smarty', 0.9663), ('YAML', 0.9487), ('Jupyter Notebook', 0.938)]
    #f['f3'] = [('Shell', 0.7976), ('Makefile', 0.6836), ('Go', 0.66), ('Python', 0.6403), ('Markdown', 0.432)]
    #f['f4'] = [('CSS', 0.9842), ('JavaScript', 0.7218), ('Less', 0.425), ('C#', 0.4161)]
    #f['f6'] = [('Java', 0.9945), ('HTML', 0.7186)]
    #f['f7'] = [('Vue', 0.8397), ('FreeMarker', 0.682)]
    #f['f11'] = [('SCSS', 0.9249)]
    #f['f5'] = [('HCL', 0.9511), ('PLSQL', 0.7543), ('Shell', 0.5739)]
    #f['f13'] = [('Go', 0.6399)]

    f['f1'] = [('Thrift', 0.9864), ('Lua', 0.9446), ('CMake', 0.9093), ('C', 0.8489), ('HTML', 0.7635), ('Others', 0.5886), ('Python', 0.5404), ('C++', 0.5293), ('Go', 0.4489)]
    f['f2'] = [('YAML', 0.9881), ('Smarty', 0.8971), ('Jupyter Notebook', 0.8492), ('Java', 0.5294)]
    f['f3'] = [('CSS', 0.9607), ('JavaScript', 0.9334), ('C#', 0.715), ('SCSS', 0.6772)]
    f['f4'] = [('Shell', 0.954), ('Makefile', 0.7459)]
    f['f5'] = [('PLSQL', 0.9286)]
    f['f6'] = [('C++', 0.8035)]
    f['f7'] = [('HTML', 0.427), ('C', 0.4265), ('Batchfile', 0.4225)]
    f['f8'] = [('Vue', 0.6958)]
    f['f9'] = [('Others', 0.5684)]

    newF['General'] = {'Thrift': 0.9974, 'C':  0.9958, 'Lua': 0.9638, 'CMake': 0.9019, 'Others': 0.7362, 'C++': 0.6553} #0.8362 + 0.4743
    newF['Datascientist'] = {'Smarty': 0.9663, 'YAML': 0.9487, 'Jupyter Notebook': 0.93}
    newF['Documentation'] = {'Shell': 0.7976, 'Makefile': 0.6836, 'Go': 0.66, 'Python': 0.6403, 'Markdown': 0.432}
    newF['DevOps'] = {'HCL': 0.9511, 'PLSQL': 0.7543, 'Shell': 0.5739, 'Batchfile': 0.9898}
    newF['Frontend'] = {'Vue': 0.8397, 'FreeMarker': 0.682, 'SCSS': 0.9249, 'TypeScript': 0.9809}
    newF['Backend'] = {'Go': 0.6399, 'C#': 0.911}
    newF['FullStack'] = {'CSS': 0.9842, 'JavaScript': 0.7218, 'Less': 0.425, 'C#': 0.4161, 'Java': 0.9945, 'HTML': 0.7186}

    newFullF = {}
    langlist = list(theseries.columns)
    for key in list(newF.keys()):
        temp = []
        for lang in langlist:
            if lang in list(newF[key].keys()):
                temp.append(newF[key][lang])
            else:
                temp.append(0)
        newFullF[key] = temp

    theauthorvalues = list(thedict.values())[:-1]
    #print(theauthorvalues)
    #print(len(theauthorvalues))
    thefactorresult = {}
    for factor in newFullF.keys():
        thefactorvalues =  newFullF[factor]
        #print(thefactorvalues)
        #print(len(thefactorvalues))
        thesumup = 0
        for i in range(len(thefactorvalues)):
            thesumup = thesumup + theauthorvalues[i] * thefactorvalues[i]
        thescore = thesumup / (sum([x * x for x in theauthorvalues]) + sum([x * x for x in thefactorvalues]) - thesumup)
        thefactorresult[factor] = thescore
    #thefactorresult['author_email'] = author_email

    print(thefactorresult)
    return thefactorresult

def creatFactorTable(thedf, newfactorcsv):
    #df_temp = pd.read_csv('devkmeans5NEW.csv')
    #df_temp = df_temp.drop(['cluster'], 1)
    thefeatures = ['authorid', 'General', 'DataScientist', 'Documentation', 'DevOps', 'Frontend', 'Backend', 'FullStack']
    with open(newfactorcsv, 'w', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(thefeatures)
    authorlist = thedf.loc[:, 'authorid'].values.tolist()
    for author in authorlist:
        print(author)
        thefactorvalues = get6factorScoresforEach(thedf, author)
        with open(newfactorcsv, 'a', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow([author] + list(thefactorvalues.values()))

#creatFactorTable(df, 'factor_perAuthor.csv')
#makeAllProjectMSPerDeveloperSortedbyMS(df)

def getUsernamefromEmail(theemail):
    try:
        return theemail.split('@')[0]
    except:
        return np.NaN


#df = pd.read_csv('all_commits_NEW_noPatch_service_ex_lang_onlyservice_id_sum.csv')
#df['sum'] = df['additions'] + df['deletions']
#df.to_csv('all_commits_NEW_noPatch_service_ex_lang_onlyservice_id_sum.csv', index=False)
#df_gb = df.groupby(['authorid', 'lang'])['sum'].sum().unstack()
#df_gb = df_gb.fillna(0)
#df_gb.reset_index(inplace=True)
#print(df_gb.head(10))
#df_gb.to_csv('authorid_lang_sum_NEW.csv', index=False)

#df_author = pd.read_csv('authorid_lang_sum_NEW.csv')
#df['authorid'] = df['author_email'].apply(getUsernamefromEmail)
#df.to_csv('all_commits_NEW_noPatch_service_ex_lang_onlyservice_id.csv', index=False)
#creatFactorTable(df_author, 'factor_perAuthorid_9.csv')


#df_factor = pd.read_csv('factor_perAuthorid_9.csv')
#print(df_factor.head())
#print(df_factor.shape)

#df = pd.read_csv('all_commits_NEW_noPatch_service_ex_lang_onlyservice_id_sum.csv')
#print(df.head())
#print(df.shape)

#df_gb = df.groupby(['project', 'service', 'authorid']).sum()
#df_gb.reset_index(inplace=True)
#df_gb = df_gb.loc[:, ['project', 'service', 'authorid', 'sum']]
#df_gb.to_csv('pro_ser_author_sum.csv', index=False)

#df_role = pd.read_csv('factor_perAuthorid_9.csv')
#df_psaso = pd.read_csv('pro_ser_author_sum_ownerper.csv')

def getContributorLevel(theproserauthorsumdf):
    theperclist = []
    for i in range(len(theproserauthorsumdf)):
        theproject = theproserauthorsumdf.loc[i, 'project']
        theservice = theproserauthorsumdf.loc[i, 'service']
        theauthor = theproserauthorsumdf.loc[i, 'authorid']
        thesum = theproserauthorsumdf.loc[i, 'sum']
        thelistofsums = theproserauthorsumdf.loc[(theproserauthorsumdf['project'] ==theproject) & (theproserauthorsumdf['service'] ==theservice), 'sum'].values.tolist()
        theperclist.append(round(thesum/sum(thelistofsums),3))
    theproserauthorsumdf['ownerper'] = theperclist
    theproserauthorsumdf.to_csv('pro_ser_author_sum_ownerper.csv', index=False)

def assignroles(theproserauthorsumperdf):
    therolelist = []
    for i in range(len(theproserauthorsumperdf)):
        theproject = theproserauthorsumperdf.loc[i, 'project']
        theservice = theproserauthorsumperdf.loc[i, 'service']
        theauthor = theproserauthorsumperdf.loc[i, 'authorid']
        thesum = theproserauthorsumperdf.loc[i, 'sum']
        theper = theproserauthorsumperdf.loc[i, 'ownerper']
        theserviceperlist = theproserauthorsumperdf.loc[(theproserauthorsumperdf['project'] ==theproject) & (theproserauthorsumperdf['service'] ==theservice), 'ownerper'].values.tolist()
        if theper == max(theserviceperlist):
            therolelist.append('Leader')
        elif theper >= 0.05:
            therolelist.append('Major')
        else:
            therolelist.append('Minor')
    theproserauthorsumperdf['ownership'] = therolelist
    theproserauthorsumperdf.to_csv('pro_ser_author_sum_ownerper_ownership.csv', index=False)



#df_role = pd.read_csv('factor_perAuthorid_9.csv')
#df_psaso = pd.read_csv('pro_ser_author_sum_ownerper_ownership.csv')
#df_merge = pd.merge(df_role, df_psaso, on='authorid', how='right')
#df_merge.to_csv('merged_pro_ser_author_sum_ownerper_ownership_factor.csv', index=False)

#df_merge = pd.read_csv('merged_pro_ser_author_sum_ownerper_ownership_factor.csv')
#print(df_merge.head())

###################################### Coupling Contributors ######################################

def getCoupling_BetweenDate_byAuthorid(theproject, thecommitdf, thetimefrom, thetimeto):
    def Union(lst1, lst2):
        final_list = list(set(lst1) | set(lst2))
        return final_list
    thefeatures = ['project', 'service1', 'service2', 'authorid', 'coupling']
    csvname = '_'.join(theproject.split('/')) + '_authorCoupling_' + thetimefrom + '_' + thetimeto + '.csv'
    with open(csvname, 'w', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(thefeatures)
    ms_commit_df = thecommitdf.loc[(thecommitdf['author_date'] <= thetimeto) & (thecommitdf['author_date'] > thetimefrom) & (thecommitdf['project']==theproject)]
    ms_commit_df.dropna(subset=['service'], inplace=True)
    ms_commit_df.sort_values(by=['author_date'], inplace=True)
    ms_commit_df = ms_commit_df.loc[:, ['commit_sha', 'authorid', 'author_date', 'service', 'sum']]
    ms_commit_df_gb = ms_commit_df.groupby(['author_date', 'commit_sha', 'authorid', 'service']).sum()
    ms_commit_df_gb.reset_index(inplace=True)
    print(ms_commit_df_gb)
    servicelist = list(ms_commit_df['service'].unique())
    servicelist = sorted(servicelist)
    print(servicelist)
    for i in range(len(servicelist))[:-1]:
        print(servicelist[i])
        for j in range(len(servicelist))[i+1:]:
            print(servicelist[j])
            ms_commit_df_gb = ms_commit_df_gb.loc[
                              (ms_commit_df_gb['service'] == servicelist[i]) | (ms_commit_df_gb['service'] == servicelist[j]), :]
            authorlist1 = list(set(ms_commit_df_gb.loc[ms_commit_df_gb['service'] == servicelist[i], 'authorid'].values.tolist()))
            authorlist2 = list(set(ms_commit_df_gb.loc[ms_commit_df_gb['service'] == servicelist[j], 'authorid'].values.tolist()))
            coupleauthors = [x for x in authorlist1 if x in authorlist2]
            allauthors = Union(authorlist1, authorlist2)
            # authorcouplinglist = []
            for author in allauthors:
                ms_commit_df_gb_author = ms_commit_df_gb.loc[ms_commit_df_gb['authorid'] == author, :]
                serviceseq = ms_commit_df_gb_author.loc[:, 'service'].values.tolist()
                switchcount = 0
                authorcoupling = 0
                for k in range(len(serviceseq) - 1):
                    if serviceseq[k] == serviceseq[k + 1]:
                        continue
                    else:
                        switchcount = switchcount + 1
                commitcount = len(serviceseq)
                try:
                    weight = switchcount / ((commitcount - 1) * 2)
                except:
                    weight = 0
                sumcontribution_m1 = sum(
                    ms_commit_df_gb_author.loc[ms_commit_df_gb_author['service'] == servicelist[i], 'sum'].values.tolist())
                sumcontribution_m2 = sum(
                    ms_commit_df_gb_author.loc[ms_commit_df_gb_author['service'] == servicelist[j], 'sum'].values.tolist())
                try:
                    authorcoupling = (2 * sumcontribution_m1 * sumcontribution_m2 / (
                                sumcontribution_m1 + sumcontribution_m2) * weight)
                except:
                    authorcoupling = 0
                with open(csvname, 'a', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile, delimiter=',')
                    writer.writerow([theproject, servicelist[i], servicelist[j], author, authorcoupling])


def getCouplingContritutors(thecommitdf, thetimefrom, thetimeto):
    #newcsv = f"{theproject.split('/')[0]}_{theproject.split('/')[1]}_heatmap_{thetimefrom}_{thetimeto}.csv"
    projectlist = list(thecommitdf['project'].unique())
    for project in projectlist:
        #print(project)
        getCoupling_BetweenDate_byAuthorid(project, thecommitdf, thetimefrom, thetimeto)


#getCouplingContritutors(df_all_commits, '2018-01-01', '2023-12-31')


#getCoupling_BetweenDate_byAuthorid('aws-containers/eks-app-mesh-polyglot-demo', df_all_commits, '2018-01-01', '2023-12-31')
#getCouplingContritutors(df_all_commits, '2018-01-01', '2023-12-31')

#all_authorcoupling_files = glob.glob("EsoccExt/authorcoupling/*.csv")
#df_all_ac = pd.concat((pd.read_csv(f) for f in all_authorcoupling_files), ignore_index=True)
#print(df_all_ac.head())
#print(df_all_ac.shape)
#df_all_ac.to_csv('author_coupling.csv', index=False)

#df_ac = pd.read_csv('author_coupling.csv')
#df_ac_gb = df_ac.groupby(['authorid'])['coupling'].sum().reset_index()
#df_merge_ac_owner = pd.merge(df_owner, df_ac_gb, on='authorid', how='left')
#df_merge_ac_owner.to_csv('merged_pro_ser_author_sum_ownerper_ownership_factor_coupling.csv', index=False)

def averageCouplingEachYear(theproject, thecommitdf, yearlist):
    #newcsv = f"{theproject.split('/')[0]}_{theproject.split('/')[1]}_heatmap_{thetime}.csv"
    theprojectcoupling = [theproject]
    for i in range(len(yearlist)-1):
        ms_commit_df = thecommitdf.loc[
            (thecommitdf['author_date'] >= yearlist[i]) & (thecommitdf['author_date'] < yearlist[i+1]) & (
                        thecommitdf['project'] == theproject)]
        # servicelist = list(set([x.split('/')[-1] for x in ms_commit_df.loc[:, 'project'].values.tolist()]))
        #print(ms_commit_df.shape)
        ms_commit_df.dropna(subset=['service'], inplace=True)
        servicelist = list(set(ms_commit_df.loc[:, 'service'].values.tolist()))
        servicelist = sorted(servicelist)
        # features = [' '] + servicelist
        # with open('yearly_coupling.csv', 'a', encoding='utf-8') as csvfile:
        #    writer = csv.writer(csvfile, delimiter=',')
        #    writer.writerow(['project', 'year1', 'year2', 'year3', 'year4', 'year5', 'year6'])
        row = []
        for m in range(len(servicelist))[:-1]:
            for n in range(len(servicelist))[m + 1:]:
                row.append(getCoupling_BetweenDate(theproject, thecommitdf, yearlist[i], yearlist[i+1], servicelist[m], servicelist[n]))
        #print(row)
        #print(servicelist)
        try:
            theprojectcoupling.append(round(sum(row) / len(row), 3))
        except:
            theprojectcoupling.append(0)
    return theprojectcoupling

def getCouplingEvoTable(thecommitdf):
    projectlist = list(thecommitdf['project'].unique())
    with open('yearly_coupling.csv', 'a', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(['project', 'year1', 'year2', 'year3', 'year4', 'year5', 'year6'])
    for project in projectlist:
        with open('yearly_coupling.csv', 'a', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(averageCouplingEachYear(project, thecommitdf, theyearlist))

theyearlist = ['2018-01-01','2019-01-01','2020-01-01','2021-01-01','2022-01-01','2023-01-01','2024-01-01']
#print(averageCouplingEachYear('MongkonEiadon/VehicleTracker', df_all_commits, theyearlist))

#print(df_all_commits.loc[(df_all_commits['author_date']>='2019-01-01') & (df_all_commits['author_date']<'2020-01-01') &(df_all_commits['project']=='MongkonEiadon/VehicleTracker')])

#getCouplingEvoTable(df_all_commits)
def makeTables():
    thedict = {'project': [], 'size': []}
    for project in listofprojects38:
        print(project)
        if project == 'https://github.com/EYBlockchain/nightfall':
            project = 'https://github.com/EYBlockchain/nightfall_3'
        theProjectQuery = 'api.github.com/repos/'.join(project.split('github.com/'))
        p_search = requests.get(theProjectQuery, headers=headers)
        project_info = p_search.json()
        thedict['project'].append(project.split('github.com/')[-1])
        thedict['size'].append(project_info['size'])

    df_py = pd.DataFrame(thedict)
    df_py.to_csv('project_size.csv', index=False)

#df_owner = pd.read_csv('merged_pro_ser_author_sum_ownerper_ownership_factor.csv')
#df_night3 = df_all_commits.loc[df_all_commits['project'] == 'EYBlockchain/nightfall_3',:]
#df_night3 = df_night3.loc[df_night3['filename'].str.contains('ui'),:]
#print(df_night3.head())

#df_all_commits_gb = df_all_commits.groupby(['project']).nunique()
#df_all_commits_gb.reset_index(inplace=True)
#print(df_all_commits_gb)
#df_all_commits_gb.to_csv('project_committers.csv', index=False)


#print(df_selected) # number of developers, number of commits


def getOCListofSelectProjects():
    allfiles = glob.glob("./EsoccExt/heatmap/*.csv")
    allfiles.sort()
    theOClist = []
    for ocfile in allfiles:
        #print(ocfile)
        try:
            df_temp = pd.read_csv(ocfile)
            df_temp.drop(df_temp.columns[0], axis=1, inplace=True)
            df_temp['Total'] = df_temp.sum(axis=1)
            #print(df_temp)
            #print(df_temp['Total'].sum(axis=0)/(df_temp.shape[0]*(df_temp.shape[0]-1)/2))
            theOClist.append(df_temp['Total'].sum(axis=0)/(df_temp.shape[0]*(df_temp.shape[0]-1)/2))
        except:
            theOClist.append(0)
        #print(df_temp.shape[0]*(df_temp.shape[0]-1)/2)
    #print(theOClist)
    return theOClist

#print(df_service.loc[df_service['project']=="EYBlockchain/nightfall"])

#df = pd.read_csv("./OldData/all_commits_NEW_noPatch_service_ex_lang_onlyservice_id_sum.csv")
#df_new = df.loc[df['author_date']<"2019-01-01",:]
#print(df.shape)
#print(df.head())
#df_g = df_new.groupby('project').count()
#print(df_g)
#df_select has the projects, n_developers, total_n_commits, 12month_n_commits



#df_selected.sort_values('github_url', inplace=True)
#df_selected["theOClist"] = getOCListofSelectProjects()
#df_selected.sort_values('theOClist', inplace=True)
#print(df_selected)
#print(df_selected['n_developers'].corr(df_selected['theOClist']))
#print(df_selected['total_n_commits'].corr(df_selected['theOClist']))
#print(df_selected['12_moths_n_commits'].corr(df_selected['theOClist']))



