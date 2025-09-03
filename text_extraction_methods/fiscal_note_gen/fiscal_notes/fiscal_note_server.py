from flask import Flask, render_template, jsonify
import json
import os

app = Flask(__name__)

# The directory where this script is located and where the JSON files are.
# Use absolute path to avoid issues with current working directory
script_dir = os.path.dirname(os.path.abspath(__file__))

# Ordered list of fiscal note JSON files
fiscal_note_files = [
    "HB400.json",
    "HB400_TESTIMONY_JHA_01-30-25_.json",
    "HB400_HSCR286_.json",
    "HB400_TESTIMONY_FIN_03-05-25_.json",
    "HB400_HD1.json",
    "HB400_HD1_HSCR1171_.json",
    "HB400_HD1_TESTIMONY_JDC_03-19-25_.json",
    "HB400_SD1.json",
    "HB400_SD1_SSCR1253_.json",
    "HB400_SD1_TESTIMONY_WAM_03-31-25_.json",
    "HB400_SD2.json",
    "HB400_SD2_SSCR1841_.json",
    "HB400_CD1.json",
    "HB400_CD1_CCR157_.json"
]

timeline_data = [
    {'date': '1/16/2025', 'text': 'Pending introduction.', 'documents': []},
    {'date': '1/17/2025', 'text': 'Introduced and Pass First Reading.', 'documents': ['HB400.json']},
    {'date': '1/21/2025', 'text': 'Referred to JHA, FIN, referral sheet 1', 'documents': []},
    {'date': '1/24/2025', 'text': 'Bill scheduled to be heard by JHA on Thursday, 01-30-25 2:00PM in House conference room 325 VIA VIDEOCONFERENCE.', 'documents': ['HB400_TESTIMONY_JHA_01-30-25_.json']},
    {'date': '1/30/2025', 'text': 'The committee on JHA recommend that the measure be PASSED, UNAMENDED. The votes were as follows: 8 Ayes: Representative(s) Tarnas, Poepoe, Belatti, Kahaloa, Perruso, Takayama, Garcia, Shimizu; Ayes with reservations: none;  Noes: none; and 3 Excused: Representative(s) Cochran, Hashem, Todd.', 'documents': []},
    {'date': '2/10/2025', 'text': 'Reported from JHA (Stand. Com. Rep. No. 286), recommending passage on Second Reading and referral to FIN.', 'documents': ['HB400_HSCR286_.json']},
    {'date': '2/10/2025', 'text': 'Passed Second Reading and referred to the committee(s) on FIN with none voting aye with reservations; none voting no (0) and Representative(s) Belatti, Cochran, Kila, Ward excused (4).', 'documents': []},
    {'date': '3/3/2025', 'text': 'Bill scheduled to be heard by FIN on Wednesday, 03-05-25 9:00AM in House conference room 308 VIA VIDEOCONFERENCE.', 'documents': ['HB400_TESTIMONY_FIN_03-05-25_.json']},
    {'date': '3/5/2025', 'text': 'The committee on FIN recommend that the measure be PASSED, WITH AMENDMENTS. The votes were as follows: 14 Ayes: Representative(s) Yamashita, Takenouchi, Grandinetti, Holt, Keohokapu-Lee Loy, Kitagawa, Kusch, Lamosao, Lee, M., Miyake, Morikawa, Templo, Alcos, Reyes Oda; Ayes with reservations: none;  Noes: none; and 2 Excused: Representative(s) Hussey, Ward.', 'documents': []},
    {'date': '3/10/2025', 'text': 'Reported from FIN (Stand. Com. Rep. No. 1171) as amended in HD 1, recommending passage on Third Reading.', 'documents': ['HB400_HD1.json', 'HB400_HD1_HSCR1171_.json']},
    {'date': '3/10/2025', 'text': 'Forty-eight (48) hours notice Wednesday,  03-12-25.', 'documents': []},
    {'date': '3/12/2025', 'text': 'Passed Third Reading as amended in HD 1 with none voting aye with reservations; none voting no (0) and Representative(s) Alcos, Cochran, Holt, Sayama, Ward excused (5).  Transmitted to Senate.', 'documents': []},
    {'date': '3/13/2025', 'text': 'Received from House (Hse. Com. No. 382).', 'documents': []},
    {'date': '3/13/2025', 'text': 'Passed First Reading.', 'documents': []},
    {'date': '3/13/2025', 'text': 'Referred to JDC, WAM.', 'documents': []},
    {'date': '3/14/2025', 'text': 'The committee(s) on JDC has scheduled a public hearing on 03-19-25 9:45AM; Conference Room 016 & Videoconference.', 'documents': ['HB400_HD1_TESTIMONY_JDC_03-19-25_.json']},
    {'date': '3/19/2025', 'text': 'The committee(s) on  JDC recommend(s) that the measure be PASSED, WITH AMENDMENTS.  The votes in JDC were as follows: 4 Aye(s): Senator(s) Rhoads, Gabbard, San Buenaventura, Awa; Aye(s) with reservations: none ; 0 No(es): none; and 1 Excused: Senator(s) Chang.', 'documents': []},
    {'date': '3/21/2025', 'text': 'Reported from JDC (Stand. Com. Rep. No. 1253) with recommendation of passage on Second Reading, as amended (SD 1) and referral to WAM.', 'documents': ['HB400_SD1.json', 'HB400_SD1_SSCR1253_.json']},
    {'date': '3/21/2025', 'text': 'Report adopted; Passed Second Reading, as amended (SD 1) and referred to WAM.', 'documents': []},
    {'date': '3/24/2025', 'text': 'The committee(s) on WAM will hold a public decision making on 03-31-25 10:01AM; Conference Room 211 & Videoconference.', 'documents': ['HB400_SD1_TESTIMONY_WAM_03-31-25_.json']},
    {'date': '3/31/2025', 'text': 'The committee(s) on  WAM recommend(s) that the measure be PASSED, WITH AMENDMENTS.  The votes in WAM were as follows: 13 Aye(s): Senator(s) Dela Cruz, Moriwaki, Aquino, DeCoite, Elefante, Hashimoto, Inouye, Kanuha, Kidani, Kim, Lee, C., Wakai, Fevella; Aye(s) with reservations: none ; 0 No(es): none; and 0 Excused: none.', 'documents': []},
    {'date': '4/4/2025', 'text': 'Reported from WAM (Stand. Com. Rep. No. 1841) with recommendation of passage on Third Reading, as amended (SD 2).', 'documents': ['HB400_SD2.json', 'HB400_SD2_SSCR1841_.json']},
    {'date': '4/4/2025', 'text': '48 Hrs. Notice 04-08-25.', 'documents': []},
    {'date': '4/8/2025', 'text': 'Report adopted; Passed Third Reading, as amended (SD  2). Ayes, 25; Aye(s) with reservations: none .  Noes, 0 (none). Excused, 0 (none).  Transmitted to House.', 'documents': []},
    {'date': '4/8/2025', 'text': 'Returned from Senate (Sen. Com. No.  628) in amended form (SD 2).', 'documents': []},
    {'date': '4/10/2025', 'text': 'House disagrees with Senate amendment (s).', 'documents': []},
    {'date': '4/11/2025', 'text': 'Received notice of disagreement (Hse. Com. No. 704).', 'documents': []},
    {'date': '4/14/2025', 'text': 'House Conferees Appointed: Tarnas, Yamashita Co-Chairs; Poepoe, Takenouchi, Garcia.', 'documents': []},
    {'date': '4/15/2025', 'text': 'Senate Conferees Appointed: Rhoads Chair; Moriwaki Co-Chair; Awa.', 'documents': []},
    {'date': '4/15/2025', 'text': 'Received notice of appointment of House conferees (Hse. Com. No. 732).', 'documents': []},
    {'date': '4/15/2025', 'text': 'Received notice of Senate conferees (Sen. Com. No. 790).', 'documents': []},
    {'date': '4/16/2025', 'text': 'Bill scheduled for Conference Committee Meeting on Thursday, 04-17-25 3:46PM in conference room 325.', 'documents': []},
    {'date': '4/17/2025', 'text': 'Conference Committee Meeting will reconvene on Monday 04-21-25 2:05PM in conference room 325.', 'documents': []},
    {'date': '4/21/2025', 'text': 'The Conference Committee recommends that the measure be Passed, with Amendments. The votes were as follows: 5 Ayes: Representative(s) Tarnas, Yamashita, Poepoe, Takenouchi, Garcia; Ayes with reservations: none; 0 Noes: none; and 0 Excused: none.', 'documents': []},
    {'date': '4/21/2025', 'text': 'The Conference committee recommends that the measure be PASSED, WITH AMENDMENTS. The votes of the Senate Conference Managers were as follows: 2 Aye(s): Senator(s) Rhoads, Moriwaki; Aye(s) with reservations: none ; 0 No(es): none; and 1 Excused: Senator(s) Awa.', 'documents': []},
    {'date': '4/21/2025', 'text': 'Conference Committee Meeting will reconvene on Monday, 04-21-25 at 5:10PM in Conference Room 309.', 'documents': []},
    {'date': '4/25/2025', 'text': 'Reported from Conference Committee (Conf Com. Rep. No. 157) as amended in (CD 1).', 'documents': ['HB400_CD1.json', 'HB400_CD1_CCR157_.json']},
    {'date': '4/25/2025', 'text': 'Forty-eight (48) hours notice Wednesday, 04-30-25.', 'documents': []},
    {'date': '4/30/2025', 'text': 'Passed Final Reading, as amended (CD 1). Ayes, 25; Aye(s) with reservations: none . 0 No(es): none.  0 Excused: none.', 'documents': []},
    {'date': '4/30/2025', 'text': 'Passed Final Reading as amended in CD 1 with none voting aye with reservations; none voting no (0) and Representative(s) Cochran, Pierick excused (2).', 'documents': []},
    {'date': '5/1/2025', 'text': 'Received notice of Final Reading (Sen. Com. No. 888).', 'documents': []},
    {'date': '5/1/2025', 'text': 'Transmitted to Governor.', 'documents': []},
    {'date': '5/2/2025', 'text': 'Received notice of passage on Final Reading in House (Hse. Com. No. 821).', 'documents': []},
    {'date': '6/26/2025', 'text': 'Act 227, on 06/26/2025 (Gov. Msg. No. 1329).', 'documents': []}
]


@app.route('/')
def index():
    fiscal_notes_data = []
    for filename in fiscal_note_files:
        try:
            # Construct the full path to the json file
            file_path = os.path.join(script_dir, filename)
            with open(file_path, 'r') as f:
                data = json.load(f)
                fiscal_notes_data.append({
                    'filename': filename,
                    'data': data
                })
        except FileNotFoundError:
            fiscal_notes_data.append({
                'filename': filename,
                'data': 'File not found.'
            })
        except json.JSONDecodeError:
            fiscal_notes_data.append({
                'filename': filename,
                'data': 'Invalid JSON format.'
            })

    # Assuming the template is in a 'templates' subdirectory relative to this script
    template_folder = os.path.join(script_dir, 'templates')
    app.template_folder = template_folder
    return render_template('index.html', fiscal_notes=fiscal_notes_data, timeline=timeline_data)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
