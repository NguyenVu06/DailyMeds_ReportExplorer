#%%

import streamlit as st  
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import requests



#%%
st.title("DailyMeds Report Explorer")


st.subheader("Nguyen Dao Vu")
st.caption("Version 1.0") # added transaction quantity filter
#%%

# ask user to type in drug or drugs names
with st.sidebar:
    drug_name_input = st.text_input("Enter drug name(s), separate by comma: ")
    if not drug_name_input:
        st.warning("Please enter drug name(s)")
        st.stop()
    st.success("Scraping data for: {}".format(drug_name_input))
    drug_names = drug_name_input.split(",")

    route_choice = st.radio("Route of Administration: ", ("Intravenous", "ALL"))

    packaging_option = st.checkbox("get me packaging info ")


st.write(route_choice.upper())

LINK_ROOT = "https://dailymed.nlm.nih.gov"
SEARCH_URL = "https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query={}&pagesize=500&page=1"


#get the links of the drugs entered by the user and return a dictionary of the links with API names as keys
def get_links(drugs):
    drugs_dict = {}
    for d in drugs:
        r = requests.get(SEARCH_URL.format(d.lower())) #connect to URL
        soup = BeautifulSoup(r.content, "html.parser") #parse HTML to BeautifulSoup object
        drugslinks = soup.find_all("a", {"class": "drug-info-link"}) #find all links with class "drug-info-link" 
        links = [LINK_ROOT + link.get("href") for link in drugslinks] #get the href attribute of each link
        drugs_dict[d.upper()] = links

    return drugs_dict


# display number of links found per drug on streamlit page  
drugs_dict = get_links(drug_names)
for k, v in drugs_dict.items():
    st.write(f"{k}: {len(v)}"+" total links found")
# load and manipulate data

# Parse at individual link for excipients infomation:
@st.cache
def get_inactives(urls_list, route_choice_in):
    store_list = []

    

    for l in urls_list:
        r_indi = requests.get(l)
        soup_indi = BeautifulSoup(r_indi.content, "html.parser")
        if route_choice_in == "Intravenous":
            intravenous = soup_indi.find(string="INTRAVENOUS") is not None
        else:
            intravenous = True

        if (soup_indi.find("li", {"class": "human"}) is not None) and (intravenous): #check if human drugs
            try:
                x = soup_indi.find(string="Inactive Ingredients").find_parent("table") #find the table with the string "Inactive Ingredients" as caption and its parent
                
                inactives = x.find_all("td", {"class":"formItem"})
                excipients_names = [inactives[i].text.strip().upper() for i in range(0,len(inactives),2) if inactives[i].text.strip() != ""]
                excipients_conc = [inactives[i].string.replace("\xa0","") for i in range(1,len(inactives),2) if inactives[i].string is not None]
                excipient_dict = dict(zip(excipients_names, excipients_conc))

                store_list.append(excipient_dict)
            except AttributeError:
                pass

        else:
            continue

    return store_list

# Create a output file with the excipients for each drug
output_dict = {}
for k, v in drugs_dict.items():
    output_dict[k] = get_inactives(v, route_choice)

    st.write(f"{k}: {len(output_dict[k])} {route_choice} formulations found")


# build summary table
drug_name = []
drug_excipients = []
drug_exp_conc = []
drug_configuration = []
# get unique excipients for each drug
drugs_dict_unique_excipients = {}

for k, v in output_dict.items():
    config_idx = 0
    for d in v:
        drug_excipients = drug_excipients + list(d.keys())
        drug_exp_conc = drug_exp_conc + list(d.values())
        drug_name = drug_name + ([k]*len(list(d.keys())))
        drug_configuration = drug_configuration + ([config_idx]*len(list(d.keys())))
        config_idx += 1


    uni_ls = []
    for i in v:
        uni_ls = list(set(uni_ls + list(i.keys())))
    
    unii ={u.split(" (UNII:")[1].replace(")","").strip() : u.split(" (UNII:")[0] for u in uni_ls}

    drugs_dict_unique_excipients[k] = unii    


# make data table from 4 lists
df = pd.DataFrame({'drug_name': drug_name, 'drug_excipients': drug_excipients, 'drug_exp_conc': drug_exp_conc, 'drug_configuration': drug_configuration})

st.dataframe(df)

def convert_df(df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv().encode('utf-8')

csv = convert_df(df)
#download csv file of excipients
st.download_button(
     label="Download Formulation data as CSV",
     data=csv,
     file_name='excipients.csv',
     mime='text/csv',
 )

#download unique excipients
unique_excipients = ""
for k, v in drugs_dict_unique_excipients.items():
        unique_excipients = unique_excipients.join(k + ": " + str(v) + "\n")

st.download_button("Download unique excipients", data=unique_excipients, file_name="unique_excipients.txt")



#package info
# look at individual links packaging:
@st.cache
def get_packaging(urls_list):
    ndcs = []
    pack_config = []
    date_released = []

    ingr_names = []
    basis_str = []
    strengths = []

    for l in urls_list:
        r_indi = requests.get(l)
        soup_indi = BeautifulSoup(r_indi.content, "html.parser")
        if (soup_indi.find("li", {"class": "human"}) is not None) and (soup_indi.find(string="INTRAVENOUS") is not None): #check if human drugs
            try:
                x = soup_indi.find(string="Packaging").find_parent("table") #find the table with the string "Packaging" as caption and its parent
                
                inactives = x.find_all("td", {"class":"formItem"})

                ndcs.append([inactives[i].text.strip() for i in range(0,len(inactives),4) if inactives[i].text.strip() != ""])

                pack_config.append([inactives[i].string.replace("\xa0","") for i in range(1,len(inactives),4) if inactives[i].string is not None])

                date_released.append([inactives[i].string.replace("\xa0","") for i in range(2,len(inactives),4) if inactives[i].string is not None])

            except AttributeError:
                pass

            try:
                active_con = soup_indi.find(string="Active Ingredient/Active Moiety").find_parent("table") #find the table with the string "Active Ingredients" as caption and its parent

                actives = active_con.find_all("td", {"class":"formItem"})

                ingr_names.append([actives[i].text.strip() for i in range(0,len(actives),3) if actives[i].text.strip() != ""])

                basis_str.append([actives[i].string.replace("\xa0","") for i in range(1,len(actives),3) if actives[i].string is not None])

                strengths.append([actives[i].string.replace("\xa0","") for i in range(2,len(actives),3) if actives[i].string is not None])



            except AttributeError:
                pass

        else:
            continue

    return ndcs, pack_config, date_released, ingr_names, basis_str, strengths


if packaging_option:
    #get all configurations for each drug
    drug_name = []
    drug_ndc = []
    drug_pack_config = []
    drug_date_released = []
    drug_ingr_names = []
    drug_basis_str = []
    drug_strengths = []
    for dr in drugs_dict:
        n, p, d, ing, b, s = get_packaging(drugs_dict[dr])
        drug_name = drug_name + [dr]*len(n)
        drug_ndc = drug_ndc + n
        drug_pack_config = drug_pack_config + p
        drug_date_released = drug_date_released + d
        drug_ingr_names = drug_ingr_names + ing
        drug_basis_str = drug_basis_str + b
        drug_strengths = drug_strengths + s

    # make data table from all lists
    df_packing = pd.DataFrame({'drug_name': drug_name, 'drug_ndc': drug_ndc, 'drug_pack_config': drug_pack_config, 'drug_date_released': drug_date_released, 'drug_ingr_names': drug_ingr_names, 'drug_basis_str': drug_basis_str, 'drug_strengths': drug_strengths})

    csv_packing = convert_df(df_packing)

    #download csv file of packaging
    st.download_button( 
        label="Download Packaging data as CSV", 
        data=csv_packing, 
        file_name='packaging.csv', 
        mime='text/csv')

