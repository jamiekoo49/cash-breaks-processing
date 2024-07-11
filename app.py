from flask import Flask, render_template, request, send_file
import pandas as pd
import os

app = Flask(__name__)

def load_and_prepare_wso(wso_name, wso_lxid, wso_issuer, wso_amount):
    print("Loading WSO data")
    wso = pd.read_csv(wso_name)
    print("WSO data loaded successfully")
    columns = [wso_lxid, wso_issuer, wso_amount]
    wso = wso[columns]
    wso = wso.rename(columns={
        wso_lxid: 'LXID',
        wso_issuer: 'Issuer Name',
        wso_amount: 'Quantity Traded'
    })
    return wso

def load_and_prepare_usb(usb_name, sheet_name, usb_lxid, usb_issuer, usb_amount, usb_num_rows):
    print("Loading Trustee data")
    usb = pd.read_excel(usb_name, sheet_name=sheet_name, skiprows=usb_num_rows, engine='openpyxl')
    print("Trustee data loaded successfully")
    columns = [usb_lxid, usb_issuer, usb_amount]
    usb = usb[columns]
    usb[usb_amount] = usb[usb_amount].astype(str).str.replace(',', '').apply(pd.to_numeric, errors='coerce')
    usb = usb.rename(columns={
        usb_lxid: 'LXID',
        usb_issuer: 'Issuer Name',
        usb_amount: 'Quantity Traded'
    })
    return usb

def aggregate_usb_data(usb):
    print("Aggregating Trustee data")
    return usb.groupby(['LXID', 'Issuer Name'], as_index=False)['Quantity Traded'].sum()

def merge_data(wso, usb_agg):
    print("Merging data")
    columns = ['LXID', 'Quantity Traded']
    wso_new = wso[columns]
    usb_agg_new = usb_agg[columns]
    merged = pd.merge(wso_new, usb_agg_new, on='LXID', how='outer', suffixes=('_wso', '_trustee'))
    merged['Quantity Traded_wso'] = merged['Quantity Traded_wso'].fillna(0)
    merged['Quantity Traded_trustee'] = merged['Quantity Traded_trustee'].fillna(0)
    merged['Difference'] = merged['Quantity Traded_wso'] - merged['Quantity Traded_trustee']
    return merged

def format_number(value):
    if pd.isnull(value):
        return "0.00"
    if value < 0:
        return f"({abs(value):,.2f})"
    else:
        return f"{value:,.2f}"

def finalize_merge(merge, wso, usb_agg):
    print("Finalizing merge")
    columns = ['LXID', 'Issuer Name']
    wso_2 = wso[columns]
    usb_agg_2 = usb_agg[columns]
    final_merged = pd.merge(merge, usb_agg_2, on='LXID', how='outer')
    issuer_name_map = wso_2.set_index('LXID')['Issuer Name'].to_dict()
    final_merged['Issuer Name'] = final_merged['Issuer Name'].fillna(final_merged['LXID'].map(issuer_name_map))

    final_merged['Quantity Traded_wso'] = pd.to_numeric(final_merged['Quantity Traded_wso'])
    final_merged['Quantity Traded_trustee'] = pd.to_numeric(final_merged['Quantity Traded_trustee'])
    final_merged['Difference'] = pd.to_numeric(final_merged['Difference'])

    final_merged['Quantity Traded_wso'] = final_merged['Quantity Traded_wso'].apply(format_number)
    final_merged['Quantity Traded_trustee'] = final_merged['Quantity Traded_trustee'].apply(format_number)
    final_merged['Difference'] = final_merged['Difference'].apply(format_number)
    return final_merged[['LXID', 'Issuer Name', 'Quantity Traded_wso', 'Quantity Traded_trustee', 'Difference']]

def convert_csv(final_df, name):
    print(f"Converting to CSV: {name}")
    final_df.to_csv(name, index=False)
    print(f"CSV {name} created successfully")

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        wso_file = request.files['wso_file']
        usb_file = request.files['usb_file']
        naming_type = request.form['naming_type']

        if naming_type == 'standard':
            wso_lxid = 'Asset_LoanXIDAssetID_Name'
            wso_issuer = 'Issuer_Name'
            wso_amount = 'QuantityTraded'
        else:
            wso_lxid = request.form['wso_lxid']
            wso_issuer = request.form['wso_issuer']
            wso_amount = request.form['wso_amount']

        usb_sheet = request.form['usb_sheet']
        usb_num_rows = int(request.form['usb_num_rows'])
        usb_lxid = request.form['usb_lxid']
        usb_issuer = request.form['usb_issuer']
        usb_amount = request.form['usb_amount']
        final_name = request.form['final_name']

        upload_folder = os.path.join(os.getcwd(), 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        wso_file_path = os.path.join(upload_folder, wso_file.filename)
        usb_file_path = os.path.join(upload_folder, usb_file.filename)

        wso_file.save(wso_file_path)
        usb_file.save(usb_file_path)

        print("Files saved successfully")

        wso = load_and_prepare_wso(wso_file_path, wso_lxid, wso_issuer, wso_amount)
        usb = load_and_prepare_usb(usb_file_path, usb_sheet, usb_lxid, usb_issuer, usb_amount, usb_num_rows)
        usb_agg = aggregate_usb_data(usb)
        merge = merge_data(wso, usb_agg)
        final = finalize_merge(merge, wso, usb_agg)
        final_csv_path = os.path.join(upload_folder, final_name)
        convert_csv(final, final_csv_path)

        print("Processing complete")

        os.remove(wso_file_path)
        os.remove(usb_file_path)

        return send_file(final_csv_path, as_attachment=True, mimetype='text/csv')

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)

