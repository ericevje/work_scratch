from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

import pandas as pd
import numpy as np

import argparse

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = '18mWf_41NHGjO9si4ZmuvqOpLuF-8BuHsBgv4AzrQmCY'

WRITE_SPREADSHEET_ID = '1AVeF1YtaeyRXsPcPCU7_nw0FFy_RgoMntdLSfw40L4I'
WRITE_RANGE = ["'1_wk'!A1:Z999", "'2_wk'!A1:Z999", "'3_wk'!A1:Z999", "'4_wk'!A1:Z999", 
            "'5_wk'!A1:Z999", "'6_wk'!A1:Z999","'7_wk'!A1:Z999", "'8_wk'!A1:Z999"]

def credentials():
    # Gets credentials from google for accessing read/write access to sheets
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('sheets', 'v4', credentials=creds)

    return(creds, service)

def get_sheet_names(creds, service):
    # Call the Sheets API
    # Get the sheet names from the SheetNames sheet
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                range="'SheetNames'!A:B").execute()
    values = result.get('values', [])
    tab_names = []
    for i in range(len(values)):
        tab_names.append(values[i][0])

    return tab_names

def scan_for_line_items(creds, service, tab):
    # Scans each sheet of the master BOM and arranges into dataframe
    parent = "RC-ASY" + tab
    tab_name = "'" + tab + "'!A:K"
    # Call the Sheets API
    sheet = service.spreadsheets()
    cols = ('ENGINEER', 'PARENT', 'PARTNO', 'DESCRIPTION', 'QTY', 'VENDOR', 
        'VENDOR PARTNO', 'MANUFACTURER', 'MANUF. PARTNO', 
        'APPROX. LEAD TIME [WEEKS]', 'COST EA.', 'EXT COST', 'NOTES', 'MULTIPLIER', 
        'EXTENDED_QTY', 'QTY ORDERED', 'QTY RECEIVED')

    if tab[0] != "-":
        print("Did not attempt to parse {}".format(tab_name))
        df = pd.DataFrame(columns=cols)
        return df

    row_list = []
    try:
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                    range=tab_name).execute()
        values = result.get('values', [])
        engineer = "unknown"
        for row in values:
            try:
                for cell in row:
                    if cell == "Responsible Engineer":
                        engineer = row[row.index(cell) + 1]
                        break
                if engineer != "unknown":
                    break
            except(IndexError):
                pass

        for row in values:
            try:
                row.insert(0, parent)
                row.insert(0, engineer)
                row_list.append(row)
            except(IndexError):
                pass
    except HttpError as e:
        print("Couldn't find sheet{}".format(tab))
        pass
    row_list.append(['','','','','','','','','','','','','','','','',''])
    df = pd.DataFrame(row_list, columns=cols)
    df = clean_up_frame(df)  
    return df

def clean_up_frame(df):
    BOM_start = 0
    for index in range(0, int(len(df))):
        if df["PARTNO"].iloc[index] == "PARTNO":
            BOM_start = index + 1
            break 
    df = df[BOM_start:]
    return df

def scan_for_dates(creds, service, tab, lead_time):
    parent = "RC-ASY" + tab
    tab_name = "'" + tab + "'!A:K"
    # Call the Sheets API
    sheet = service.spreadsheets()
    cols = ('ENGINEER', 'PARENT', 'PARTNO', 'DESCRIPTION', 'QTY', 'VENDOR', 
        'VENDOR PARTNO', 'MANUFACTURER', 'MANUF. PARTNO', 
        'APPROX. LEAD TIME [WEEKS]', 'COST EA.', 'EXT COST', 'NOTES', 'MULTIPLIER', 
        'EXTENDED_QTY', 'QTY ORDERED', 'QTY RECEIVED')
    
    row_list = []
    try:
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                    range=tab_name).execute()
        values = result.get('values', [])
        engineer = "unknown"
        for row in values:
            try:
                for cell in row:
                    if cell == "Responsible Engineer":
                        engineer = row[row.index(cell) + 1]
                        break
                if engineer != "unknown":
                    break
            except(IndexError):
                pass

        for row in values:
            try:
                if row[7] == lead_time:
                    row.insert(0, parent)
                    row.insert(0, engineer)
                    row_list.append(row)
            except(IndexError):
                pass
    except HttpError as e:
        print("Couldn't find sheet{}".format(tab))
        pass
    row_list.append(['','','','','','','','','','','','','','','','',''])
    df = pd.DataFrame(row_list, columns=cols)    
    return df

def multiple_assy_check(parent, df, add_parts=1):
    try:
        final_multiplier = 0
        df_parent_as_part = df.loc[df["PARTNO"] == parent]
        empty = df_parent_as_part.empty
        if  empty != True:
            for i in range(0, len(df_parent_as_part)):
                add_parts *= int(df_parent_as_part["QTY"].iloc[i])
                new_parent = df_parent_as_part["PARENT"].iloc[i]
                add_parts *= multiple_assy_check(new_parent, df)
                final_multiplier += add_parts
            return final_multiplier
        else:
            return 1
    except KeyError:
        print("No match found")
        return final_multiplier
    except IndexError:
        print("Not a part")
        return final_multiplier
    except ValueError:
        print("not a number")
        return final_multiplier

def order_quantity(BOM_df, order_df, builds):
    for i in range(0, len(order_df["PARTNO"])):
        try:
            part_no = order_df["PARTNO"].iloc[i]

            parent = order_df["PARENT"].iloc[i]
            # print (part_no, parent)
            single_quantity = order_df["QTY"].iloc[i]

            multiplier = multiple_assy_check(parent, BOM_df)

            order_df["MULTIPLIER"].iloc[i] = int(multiplier)
            order_df["EXTENDED_QTY"].iloc[i] = int(single_quantity) * multiplier * builds
        except ValueError:
            print("single child assembly qty is not a number: {}".format(single_quantity))
    return order_df

def write_to_sheet(df, sheet_name):
    request = service.spreadsheets().values().clear(spreadsheetId=WRITE_SPREADSHEET_ID, range=sheet_name)
    response = request.execute()
    values = df
    data = [
        {
            'range': sheet_name,
            'values': values
        },
        # Additional ranges to update ...
    ]
    body = {
        'valueInputOption': "RAW",
        'data': data
    }
    result = service.spreadsheets().values().batchUpdate(
        spreadsheetId=WRITE_SPREADSHEET_ID, body=body).execute()
    print('{0} cells updated.'.format(result.get('totalUpdatedCells')))

if __name__ == '__main__':

    # Argument parser
    parser = argparse.ArgumentParser(
        description='This script extracts items and order quantities from the RC2 Master BOM.')
    parser.add_argument('lead_time', type=str,
                        help='The number for the week lead time to search the BOM for.')
    parser.add_argument('builds', type=int,
                        help='Number of builds to order for')
    parser.add_argument('update_full', type=int,
                        help='Whether (1) or not (0) to update full bom sheet')
    parser.add_argument('update_partial', type=int,
                        help='Whether (1) or not (0) to update weekly bom sheet')
    args = parser.parse_args()

    # Aquire Oauth credentials from google
    creds, service = credentials()

    # Retrieve the tab names from the BOM spreadsheet
    tab_names = get_sheet_names(creds, service)

    # Retrieve the full BOM from the spreadsheets
    full_BOM = []
    for tab in tab_names:
        full_BOM.append(scan_for_line_items(creds, service, tab))

    full_BOM_df = pd.concat(full_BOM)
    full_BOM_df['PARTNO'].replace('', np.nan, inplace=True)
    full_BOM_df.dropna(subset=['PARTNO'], inplace=True)

    order_BOM_df = order_quantity(full_BOM_df, full_BOM_df, args.builds)

    BOM_file_name = "BOM.csv" 
    full_BOM_df.to_csv(BOM_file_name, sep=',', index=False)

    full_BOM_df = full_BOM_df.reset_index()
    del full_BOM_df["index"]
    full_order_list = full_BOM_df.values.tolist()
    full_order_list.insert(0, ['ENGINEER', 'PARENT', 'PARTNO', 'DESCRIPTION', 'QTY', 'VENDOR', 
        'VENDOR PARTNO', 'MANUFACTURER', 'MANUF. PARTNO', 
        'APPROX. LEAD TIME [WEEKS]', 'COST EA.', 'EXT COST', 'NOTES', 'MULTIPLIER', 
        'EXTENDED_QTY', 'QTY ORDERED', 'QTY RECEIVED'])
    # full_order_list.insert(0, ['Last updated', ])

    if args.update_full == 1:
        print("updating full BOM sheet")
        write_to_sheet(full_order_list, "'Full'!A1:Z999")

    # Retrieve only the part numbers for the lead time desired
    order_df = []
    for tab in tab_names:
        order_df.append(scan_for_dates(creds, service, tab, args.lead_time))

    weekly_BOM_df = pd.concat(order_df)
    weekly_BOM_df['PARTNO'].replace('', np.nan, inplace=True)
    weekly_BOM_df.dropna(subset=['PARTNO'], inplace=True)

    order_BOM_df = order_quantity(full_BOM_df, weekly_BOM_df, args.builds)

    stats_file_name = "Results.csv" 
    order_BOM_df.to_csv(stats_file_name, sep=',', index=False)

    order_BOM_df = order_BOM_df.reset_index()
    del order_BOM_df["index"]
    order_list = order_BOM_df.values.tolist()
    order_list.insert(0, ['ENGINEER', 'PARENT', 'PARTNO', 'DESCRIPTION', 'QTY', 'VENDOR', 
        'VENDOR PARTNO', 'MANUFACTURER', 'MANUF. PARTNO', 
        'APPROX. LEAD TIME [WEEKS]', 'COST EA.', 'EXT COST', 'NOTES', 'MULTIPLIER', 
        'EXTENDED_QTY', 'QTY ORDERED', 'QTY RECEIVED'])

    if args.update_partial == 1:
        print("updating partial sheet")
        write_to_sheet(order_list, WRITE_RANGE[int(args.lead_time) - 1])




