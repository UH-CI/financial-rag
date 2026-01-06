#!/usr/bin/env python3
"""
Standalone RefBot - PDF Committee Assignment Tool
-------------------------------------------------
This script processes a ZIP file of legislative bills (PDFs), extracts their text,
and uses Google's Gemini 2.5 Pro model to assign appropriate committees based on
House rules and definitions.

Usage:
    python standalone_refbot.py <path_to_zip> --api-key <your_google_api_key>

Requirements:
    pip install google-generativeai pymupdf pdfplumber pytesseract pillow
"""

import os
import sys
import argparse
import zipfile
import json
import logging
import time
import shutil
import re
import io
from pathlib import Path
from typing import List, Dict, Any

# --- DEPENDENCY CHECK ---
try:
    import google.generativeai as genai
    import fitz  # PyMuPDF
    import pdfplumber
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        # Tesseract/Image is optional if not using OCR
        pass
except ImportError as e:
    print(f"❌ Missing required library: {e}")
    print("Please install requirements: pip install google-generativeai pymupdf pdfplumber pytesseract pillow")
    sys.exit(1)

# --- LOGGING CONFIG ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("RefBot")

# --- EMBEDDED CONTEXT DATA ---
# This data allows the script to run without external dependency files.

COMMITTEES_DATA = """
[
    {
        "committee_id": "AGR",
        "committee_name": "Agriculture & Food Systems",
        "description": "whose scope shall be those programs relating to the Department of Agriculture, agriculture, aquaculture, crop and livestock production, food production and distribution, agricultural parks, animal welfare, invasive species, and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "CPC",
        "committee_name": "Consumer Protection & Commerce",
        "description": "whose scope shall be those programs relating to consumer protection, the Department of Commerce and Consumer Affairs, the regulation of trade, business, professions, occupations, and utilities, the Residential Landlord-Tenant Code, condominiums, housing cooperatives, planned communities, insurance, financial institutions, and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "CAA",
        "committee_name": "Culture & Arts",
        "description": "whose scope shall be those programs related to Hawaii's multi-cultural heritage and the State Foundation on Culture and the Arts; and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "ECD",
        "committee_name": "Economic Development & Technology",
        "description": "whose scope shall be those programs relating to private sector job creation, public- private business or investment partnerships or ventures, new industry development, planning for economic development and diversification, industrial and product promotion and financial and technical assistance to business for interstate and intrastate commerce, broadband and cable communications and services, intergovernmental relations, and technology and cybersecurity, and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "EDN",
        "committee_name": "Education",
        "description": "whose scope shall be those programs relating to early childhood education, primary and secondary schools, continuing education, libraries, and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "EEP",
        "committee_name": "Energy & Environmental Protection",
        "description": "whose scope shall be those programs relating to energy resources, electric and gas utilities, the development of new energy resources, energy efficiency, and electrification of transportation; programs relating to climate change mitigation, including decarbonization, emissions reduction, and carbon sequestration; programs relating to environmental health, including air pollution, drinking water, hazardous waste, solid waste, recycling, and wastewater management; programs relating to natural resources protection and conservation; programs relating to environmental impact assessment and chapter 343, Hawaii Revised Statutes; and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "FIN",
        "committee_name": "Finance",
        "description": "whose scope shall be those programs relating to overall state financing policies, including taxation and other revenues, cash and debt management, statewide implementation of planning, programming, budgeting, and evaluation, and procurement and the Procurement Code, and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "HLT",
        "committee_name": "Health",
        "description": "whose scope shall be those programs relating to general health, maternal and child care, dental health, medical and hospital services, mental health, hospitals, community health care facilities, and communicable diseases; and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "HED",
        "committee_name": "Higher Education",
        "description": "whose scope shall be those programs relating to the University of Hawaii, the community colleges, and other institutions of post-secondary education, intercollegiate athletics, and the Waikiki Aquarium; and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "HSG",
        "committee_name": "Housing",
        "description": "whose scope shall be those programs relating to housing development financing, assistance for homebuyers and renters, affordable and rental housing, public housing, and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "HSH",
        "committee_name": "Human Services & Homelessness",
        "description": "whose scope shall be those programs relating to financial assistance, medical assistance, vocational rehabilitation, social welfare services, the general well-being of the State's elderly and youth, and juvenile correctional services, and homeless services and sheltering, and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "JHA",
        "committee_name": "Judiciary & Hawaiian Affairs",
        "description": "whose scope shall be those programs relating to the courts, crime prevention and control, penal code, criminal enforcement, police and law enforcement, prosecution, sentencing, disposition, and punishment, probation, parole, furlough, and other alternatives to incarceration, indigent legal representation and defense matters, civil law, firearms, weapons, judicial and legal questions, constitutional matters, the Attorney General, the Judiciary, individual rights, civil rights and liberties, the Civil Rights Commission, the Ethics Code, campaign spending, and elections; and persons of Hawaiian ancestry, including programs administered by the Department of Hawaiian Home Lands and the Office of Hawaiian Affairs; and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "LAB",
        "committee_name": "Labor",
        "description": "whose scope shall be those programs relating to employment, government operations and efficiency, employee pay and benefits, employee recruitment, classification and training, career development, employee performance, employment conditions, standards of conduct for employers and employees, collective bargaining in public employment, the civil service system, workers' compensation, unemployment compensation, temporary disability insurance, prepaid health care, employment opportunities, and labor- management relations in the private sector; and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "LMG",
        "committee_name": "Legislative Management",
        "description": "whose scope shall be those programs relating to the administrative operations and legislative services of the House, including the Legislative Reference Bureau, Legislative Auditor, Office of the Ombudsman, Public Access Room, the Hawaii State General Plan, and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "PBS",
        "committee_name": "Public Safety",
        "description": "whose scope shall be those programs relating to adult corrections, rehabilitation, and correctional facilities and industries; military facilities, activities, and veterans’ affairs; and emergency management, including prevention, preparation, response, and recovery from civilian emergencies and disasters, and the safety, welfare, and defense of the State and its people; and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "TOU",
        "committee_name": "Tourism",
        "description": "whose scope shall be those programs relating to tourism, including the Hawaii Convention Center, Hawaii Visitors and Convention Bureau, and Hawaii Tourism Authority, and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "TRN",
        "committee_name": "Transportation",
        "description": "whose scope shall be those programs relating to the development and maintenance of air, water, and ground transportation, infrastructure, and facilities, and other pertinent matters referred to it by the House."
    },
    {
        "committee_id": "WAL",
        "committee_name": "Water & Land",
        "description": "whose scope shall be those programs relating to climate adaptation to the actual or expected impacts of climate change; land and water resource administration and use, coastal lands, the Land Use Commission, county land use planning and zoning, the Hawaii Community Development Authority, infrastructure development, outdoor recreation, fresh water and brackish waters, small boat harbors and their infrastructure, State parks, historic sites development and protection, ocean activities and outdoor marine matters, the Coastal Zone Management Act; and other pertinent matters referred to it by the House."
    }
]
"""

FINANCE_RESP = """13.2. Committee on Finance: Special Responsibility. The Committee on Finance
shall:
(1) Have final responsibility over all programs and matters relating to the
State's financing policies, including taxation and other revenues, level
of expenditures, cash and debt management, and to the statewide
implementation of planning, programming, budgeting, and evaluation.
Subject to the provisions of these Rules, it shall consider the reports of
the fiscal officers of the State, all bills, petitions, and resolutions, those
portions of the state budget, and all other items pertaining to such
programs and matters. It shall also consider such other pertinent items
as may be referred to it by the House;
(2) Establish, within the revenue raising ability of the State, the general
level of total governmental expenditures for each fiscal year of a
biennial period and allocate to each standing committee a
proportionate part of such expenditures. Each standing committee
shall be responsible for budget review of the programs within its
jurisdiction and for making program expenditure recommendations to
the Committee on Finance. Upon receipt of the recommendations of
the other standing committees, the Committee on Finance shall review
the same to determine if, when taken as a whole, the programs and
amounts to be expended thereon are consistent with and within the
expenditure amounts it has allocated to the respective standing
committees. In making allocations to and in reviewing
recommendations, the Committee on Finance shall invite the
participation of the chair of the standing committee having primary
responsibility over the program. After review of all standing committee
recommendations, the Committee on Finance shall be responsible for
preparing the General and Supplemental Appropriations Bills for
consideration by the House; and
(3) In all other appropriation bills, inform the standing committee primarily
responsible for the program or matter under consideration, of the
amount and type of finances available. Upon receiving
recommendations for the expenditures from the appropriate standing
committee, the Committee on Finance shall review such
recommendations to determine if, when taken as a whole, the
recommendations are consistent with and within the expenditure
amounts allocated. In reviewing recommendations of the standing
committees, the Committee on Finance shall invite the participation of
the standing committee chair concerned."""

GENERAL_RESP = """
Rule 13. Standing Committees: General Responsibility; Special Responsibility
13.1. Standing Committees: General Responsibility. It shall be the duty of each
standing committee to:
(1) Consider all bills, petitions, and resolutions as may properly come
before it;
(2) Review those portions of the State's program and financial plan and
variance reports as may relate to programs over which the committee
has primary responsibility. Through informational briefings, it shall
gather information and examine those portions of the executive budget
and the General and Supplemental Appropriations Bills relating to such
programs and recommend to the Committee on Finance the programs
and amounts to be spent thereon (The executive budget and the
General and Supplemental Appropriations Bills are hereinafter
collectively referred to as the "State budget."). The recommended
programs and amounts, taken as a whole, shall be consistent with and
within the expenditure amounts allocated by the Committee on
Finance;
(3) Determine the objectives of any bill referred to it and make appropriate
recommendations, including, if proper, expenditure recommendations
on other bills referred to it by the House. Such expenditure
recommendations shall be consistent with the allocations established
by the Committee on Finance. On bills that relate to programs and
matters over which a standing committee to which they are referred
has no primary responsibility, the standing committee shall propose no
substantive change to the bill unless prior concurrence of the chair of
the committee which has the primary responsibility is first obtained. If
the chair of the standing committee, which has primary responsibility
over programs and matters of a bill, does not concur with the
substantive change to the bill affecting such programs and matters
sought to be proposed by a standing committee, any of the chairs of
the standing committees involved may submit the matter to the
Speaker for resolution. The Speaker shall meet with the chairs of the
standing committees involved, hear their differences, and settle their
differences with a decision, which shall be the final disposition of the
matter; and
(4) Review how programs over which it has primary responsibility have
been carried out in compliance with legislative direction and whether
studies, analysis, and audit should be conducted on all or part of the
program in order to define issues and recommend improvements.
Each standing committee shall also recommend amendments to
existing appropriation acts and may further recommend revenue
measures and improvements to the State's planning, programming,
budgeting, and evaluation system to the Committee on Finance."""

HOUSE_RULES = """Rule 12. Standing Committees: Description
Standing committees shall be created by resolution at the opening of the
session, or as soon thereafter as possible, to serve during the legislative
session. The standing committees therein shall be as follows:
(1) Committee on Agriculture & Food Systems, whose scope shall be
those programs relating to the Department of Agriculture, agriculture,
aquaculture, crop and livestock production, food production and
distribution, agricultural parks, animal welfare, invasive species, and
other pertinent matters referred to it by the House.
(2) Committee on Consumer Protection & Commerce, whose scope shall
be those programs relating to consumer protection, the Department of
Commerce and Consumer Affairs, the regulation of trade, business,
professions, occupations, and utilities, the Residential Landlord-Tenant
Code, condominiums, housing cooperatives, planned communities,
insurance, financial institutions, and other pertinent matters referred to
it by the House.
(3) Committee on Culture & Arts, whose scope shall be those programs
related to Hawaii's multi-cultural heritage and the State Foundation on
Culture and the Arts; and other pertinent matters referred to it by the
House.
(4) Committee on Economic Development & Technology, whose scope
shall be those programs relating to private sector job creation, public-
private business or investment partnerships or ventures, new industry
development, planning for economic development and diversification,
industrial and product promotion and financial and technical assistance
to business for interstate and intrastate commerce, broadband and
cable communications and services, intergovernmental relations, and
technology and cybersecurity, and other pertinent matters referred to it
by the House.
(5) Committee on Education, whose scope shall be those programs
relating to early childhood education, primary and secondary schools,
continuing education, libraries, and other pertinent matters referred to
it by the House.
(6) Committee on Energy & Environmental Protection, whose scope shall
be those programs relating to energy resources, electric and gas
utilities, the development of new energy resources, energy efficiency,
and electrification of transportation; programs relating to climate
change mitigation, including decarbonization, emissions reduction, and
carbon sequestration; programs relating to environmental health,
including air pollution, drinking water, hazardous waste, solid waste,
recycling, and wastewater management; programs relating to natural
resources protection and conservation; programs relating to
environmental impact assessment and chapter 343, Hawaii Revised
Statutes; and other pertinent matters referred to it by the House.
(7) Committee on Finance, whose scope shall be those programs relating
to overall state financing policies, including taxation and other
revenues, cash and debt management, statewide implementation of
planning, programming, budgeting, and evaluation, and procurement
and the Procurement Code, and other pertinent matters referred to it
by the House.
(8) Committee on Health, whose scope shall be those programs relating
to general health, maternal and child care, dental health, medical and
hospital services, mental health, hospitals, community health care
facilities, and communicable diseases; and other pertinent matters
referred to it by the House.
(9) Committee on Higher Education, whose scope shall be those programs
relating to the University of Hawaii, the community colleges, and other
institutions of post-secondary education, intercollegiate athletics, and
the Waikiki Aquarium; and other pertinent matters referred to it by the
House.
(10) Committee on Housing, whose scope shall be those programs relating
to housing development financing, assistance for homebuyers and
renters, affordable and rental housing, public housing, and other
pertinent matters referred to it by the House.
(11) Committee on Human Services & Homelessness, whose scope shall
be those programs relating to financial assistance, medical assistance,
vocational rehabilitation, social welfare services, the general well-being
of the State's elderly and youth, and juvenile correctional services, and
homeless services and sheltering, and other pertinent matters referred
to it by the House.
(12) Committee on Judiciary & Hawaiian Affairs, whose scope shall be
those programs relating to the courts, crime prevention and control,
penal code, criminal enforcement, police and law enforcement,
prosecution, sentencing, disposition, and punishment, probation,
parole, furlough, and other alternatives to incarceration, indigent legal
representation and defense matters, civil law, firearms, weapons,
judicial and legal questions, constitutional matters, the Attorney
General, the Judiciary, individual rights, civil rights and liberties, the
Civil Rights Commission, the Ethics Code, campaign spending, and
elections; and persons of Hawaiian ancestry, including programs
administered by the Department of Hawaiian Home Lands and the
Office of Hawaiian Affairs; and other pertinent matters referred to it by
the House.
(13) Committee on Labor, whose scope shall be those programs relating to
employment, government operations and efficiency, employee pay and
benefits, employee recruitment, classification and training, career
development, employee performance, employment conditions,
standards of conduct for employers and employees, collective
bargaining in public employment, the civil service system, workers'
compensation, unemployment compensation, temporary disability
insurance, prepaid health care, employment opportunities, and labor-
management relations in the private sector; and other pertinent matters
referred to it by the House.
(14) Committee on Legislative Management, whose scope shall be those
programs relating to the administrative operations and legislative
services of the House, including the Legislative Reference Bureau,
Legislative Auditor, Office of the Ombudsman, Public Access Room,
the Hawaii State General Plan, and other pertinent matters referred to
it by the House.
(15) Committee on Public Safety, whose scope shall be those programs
relating to adult corrections, rehabilitation, and correctional facilities
and industries; military facilities, activities, and veterans’ affairs; and
emergency management, including prevention, preparation, response,
and recovery from civilian emergencies and disasters, and the safety,
welfare, and defense of the State and its people; and other pertinent
matters referred to it by the House.
(16) Committee on Tourism, whose scope shall be those programs relating
to tourism, including the Hawaii Convention Center, Hawaii Visitors and
Convention Bureau, and Hawaii Tourism Authority, and other pertinent
matters referred to it by the House.
(17) Committee on Transportation, whose scope shall be those programs
relating to the development and maintenance of air, water, and ground
transportation, infrastructure, and facilities, and other pertinent matters
referred to it by the House.
(18) Committee on Water & Land, whose scope shall be those programs
relating to climate adaptation to the actual or expected impacts of
climate change; land and water resource administration and use,
coastal lands, the Land Use Commission, county land use planning
and zoning, the Hawaii Community Development Authority,
infrastructure development, outdoor recreation, fresh water and
brackish waters, small boat harbors and their infrastructure, State
parks, historic sites development and protection, ocean activities and
outdoor marine matters, the Coastal Zone Management Act; and other
pertinent matters referred to it by the House."""

LEGISLATIVE_RESP = """13.3. Committee on Legislative Management: Special Responsibility. The
Committee on Legislative Management shall:
(1) Make recommendations to the Speaker on the procedures and manner
in which the administrative operations of the House should be
conducted;
(2) Make recommendations to the Committee on Finance on the expenses
to be included in the appropriation bills providing for the expenses of
the Legislature and procedures to ensure that the expenses of the
House are in accordance with the appropriation acts providing
therefore; and
(3) Make recommendations to the Speaker on programs relating to the
establishment and operations of the House staff."""

EXAMPLES_3_SHOT = """
[
    {
        "bill_name": "HB1188",
        "bill_intro": "HB1188 HOUSE OF REPRESENTATIVES H.B. NO. 1188 THIRTY-THIRD LEGISLATURE, 2025 STATE OF HAWAII A BILL FOR AN ACT relating to teacher workforce housing . BE IT ENACTED BY THE LEGISLATURE OF THE STATE OF HAWAII: SECTION 1. The legislature finds that teachers are fundamental to shaping the future of Hawai ʻ i's keiki and communities. However, rural and underserved areas of the State still face significant challenges in attracting and retaining qualified educators due to limited affordable housing options and the State's high cost of living. The legislature further finds that challenges with teacher retention have resulted in a growing reliance on emergency hires and long-term substitutes, which can negatively affect the quality of education for students and place additional financial strain on the department of education. Addressing teacher retention is critical to reducing educational disparities and ensuring equitable access to high-quality learning opportunities for all students in public and charter schools. The legislature therefore finds that providing financial assistance for housing through a teacher workforce housing stipend program would support teacher retention in rural and underserved communities. Additionally, a stipend program would help alleviate economic burdens and encourage educators to make long-term commitments to teaching in rural and underserved communities. Accordingly, the purpose of this Act is to establish a teacher workforce housing stipend program to strengthen the teaching profession, support educational equity, and invest in the success of Hawai ʻ i's students and schools. SECTION 2. Chapter 302A, Hawaii Revised Statutes, is amended by adding a new section to part III, subpart E, to be appropriately designated and to read as follows: \\" §302A- Teacher workforce housing; stipend program; rural and underserved schools. (a) There is established a teacher workforce housing stipend program to be administered by the department to support teacher retention at any public school designated as rural or in an underserved area. (b) An individual shall be eligible for stipend consideration if the individual: (1) Is employed full-time by the department in a public or charter school in an area designated as rural or underserved; and (2) Does not own a residence within commuting distance from the school at which they are employed. (c) Stipend recipients shall receive $1,000 per month; provided that stipends awarded shall only be used only for rent or utilities. Recipients of the teacher workforce housing stipend shall submit annual documentation verifying the usage of the stipend for housing purposes pursuant to this subsection. (d) Immediately following an award of a stipend, the recipient shall commit to teaching at a school in an area designated as rural or underserved for a minimum of three years. A stipend recipient may continue to receive a stipend pursuant to this section following the completion of the designated number of years; provided that the recipient continues to meet eligibility requirements pursuant to subsection (b). (e) If the recipient fails to satisfy the work requirements in accordance with subsection (d), the recipient shall repay the total amount of the stipend funds received as a loan repayable to the department. The repayment shall be subject to the terms and conditions set by the department. (f) The department shall submit a report of its findings and recommendations, including any proposed legislation, to the legislature no later than twenty days prior to the convening of the regular session for every odd-numbered year, beginning with the regular session of 2027. \\" SECTION 3. There is appropriated out of the general revenues of the State of Hawaii the sum of $ or so much thereof as may be necessary for fiscal year 2025-2026 and the same sum or so much thereof as may be necessary for fiscal year 2026-2027 for the establishment and administration of the teacher workforce housing stipend program established pursuant to section 2 of this Act. The sums appropriated shall be expended by the department of education for the purposes of this Act. SECTION 4. New statutory material is underscored. SECTION 5. This Act shall take effect on July 1, 2025. INTRODUCED BY: _____________________________ Report Title: DOE; Teacher Workforce Housing Stipend Program; Workforce Housing; Reports; Appropriations Description: Establishes a Teacher Workforce Housing Stipend Program to support teacher retention at public and charter schools classified as rural and underserved. Requires reports to the Legislature. Appropriates funds. The summary description of legislation appearing on this page is for informational purposes only and is not legislation or evidence of legislative intent.",
        "committees": [
            "EDN",
            "HSG",
            "FIN"
        ]
    },
    {
        "bill_name": "HB1211",
        "bill_intro": "HB1211 HOUSE OF REPRESENTATIVES H.B. NO. 1211 THIRTY-THIRD LEGISLATURE, 2025 STATE OF HAWAII A BILL FOR AN ACT Relating to Workforce Development . BE IT ENACTED BY THE LEGISLATURE OF THE STATE OF HAWAII: SECTION 1. This Act shall be known and may be cited as the \\"State Internship and Workforce Development Act.\\" SECTION 2. The legislature finds that state departments and agencies face significant challenges in filling vacant positions with qualified candidates. These staff shortages lead to inefficiencies and prevent the State from optimally fulfilling its public duties. The legislature further finds that many individuals, particularly recent graduates and those pursuing new career paths, lack opportunities to gain hands-on work experience in public service roles. This presents an opportunity for the State to support workforce development while addressing vacancies in public service positions. The legislature recognizes that a structured, state-funded internship program can serve as a pipeline for recruiting and retaining skilled workers in state government. Accordingly, the purpose of this Act is to establish a state-funded internship program that provides participants with practical work experience, fosters interest in public service careers, and helps address workforce shortages in state departments and agencies. SECTION 3. Chapter 78, Hawaii Revised Statutes, is amended by adding a new section to be appropriately designated and to read as follows: \\" §78- State internship and workforce development program. (a) There is established within the department of human resources development the state internship and workforce development program. The department shall administer the program in conjunction with a designated coordinating agency. The program shall: (1) Provide paid internship opportunities within various state departments and agencies; (2) Prioritize placement in departments with significant workforce shortages; (3) Offer internships ranging in length from eighty-nine days to no longer than twelve months; and (4) Include comprehensive training, mentorship, and evaluation components. (b) The program shall be funded through annual appropriations by the legislature; provided that state departments utilizing interns shall contribute a portion of program costs based on the number of interns placed within the department, as determined by the department of human resources development. (c) Eligibility for the program shall be open to anyone who: (1) Is a resident of the State; (2) Is eighteen years of age or older; and (3) Meets specific criteria established by the department of human resources development and respective coordinating agencies. (d) Selection of internship participants shall be based on: (1) Academic achievement or relevant work experience; (2) Interest in public service careers; and (3) Alignment with departmental workforce needs. (e) As part of the program, internship participants shall: (1) Attend and actively participate in all required work experience training sessions; (2) Perform assigned duties and responsibilities in accordance with program guidelines; and (3) Adhere to workplace policies and procedures. (f) As part of the program, coordinating agency work sites shall: (1) Demonstrate need and an ability to employ participants following program completion; (2) Implement work experience training to ensure effective integration of interns into the workplace; (3) Abide by all rules and requirements of the program; (4) Ensure sufficient supervision and mentorship of interns to facilitate professional growth and development; (5) Provide meaningful and adequate work experience to help interns meet the requirements for employment in the relevant position; (6) Conduct regular performance evaluations of interns and provide feedback to the coordinating agency; (7) Collaborate with the department of human resources development to create career pathways for interns; and (8) Ensure that viable and vacant positions relative to the interns' field of study are available to participate in this program. (g) The department of human resource development shall: (1) Ensure that the experience gained through the program qualifies participants to apply for vacant positions of a similar level and scope within the hosting department; (2) Develop standardized guidelines to align internship duties with the qualifications required for full-time employment; (3) Provide ongoing support to coordinating agencies to ensure compliance with program objectives; and (4) Collaborate with coordinating agencies to create career pathways for interns. (h) As part of the program, participants shall receive: (1) A stipend or hourly wage commensurate with the role and duration of the internship; (2) Opportunities for professional development and skills training; and (3) Priority consideration for full-time employment in state government. (i) Each coordinating agency shall: (1) Develop performance metrics to evaluate the program's effectiveness in reducing workforce shortages; (2) Provide data on intern performance and retention rates for program evaluation; and (3) Submit an annual report to the legislature no later than twenty days before the convening of each regular session, detailing program participation, costs, and outcomes. (j) As used in this section: \\"Coordinating agency\\" means the participating State of Hawaii department, agency, or office hosting and employing an intern program participant. \\"Eligible participant\\" means an individual who meets established guidelines for participation in the program, including recent high school graduates, college students, post‑graduate students, and individuals seeking to transition into public service careers. \\"Internship program\\" or \\"program\\" means the State internship and workforce development program established pursuant to this section. \\"Participant\\" means an individual accepted into the internship program. \\" SECTION 4. New statutory material is underscored. SECTION 5. This Act shall take effect upon its approval. INTRODUCED BY: _____________________________ Report Title: DHRD; State Internship and Workforce Development Act; Internships; Public Service; State Departments and Agencies; Workforce Development; Vacancies; Shortages; Experience Description: Establishes within the Department of Human Resources Development the state internship and workforce development program. The summary description of legislation appearing on this page is for informational purposes only and is not legislation or evidence of legislative intent.",
        "committees": [
            "LAB",
            "FIN"
        ]
    },
    {
        "bill_name": "HB66",
        "bill_intro": "HB66 HOUSE OF REPRESENTATIVES H.B. NO. 66 THIRTY-THIRD LEGISLATURE, 2025 STATE OF HAWAII A BILL FOR AN ACT RELATING TO HUMAN SERVICES . BE IT ENACTED BY THE LEGISLATURE OF THE STATE OF HAWAII: SECTION 1. The purpose of this Act is to effectuate the title of this Act. SECTION 2. The Hawaii Revised Statutes is amended to conform to the purpose of this Act. SECTION 3. This Act shall take effect upon its approval. INTRODUCED BY: _____________________________ Report Title: Human Services; Short Form Description: Short form bill relating to human services. The summary description of legislation appearing on this page is for informational purposes only and is not legislation or evidence of legislative intent.",
        "committees": [
            "HSH"
        ]
    }
]
"""

# --- PDF EXTRACTION CLASS ---
class PDFTextExtractor:
    """
    Multi-technique PDF text extractor that adapts based on content type.
    """
    def __init__(self, pdf_path: str, contains_tables: bool, 
                 contains_images_of_text: bool, contains_images_of_nontext: bool):
        self.pdf_path = Path(pdf_path)
        self.contains_tables = contains_tables
        self.contains_images_of_text = contains_images_of_text
        self.contains_images_of_nontext = contains_images_of_nontext
        
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    def extract_all_pages(self) -> List[Dict[str, Any]]:
        page_results = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf_plumber_doc:
                pymupdf_doc = fitz.open(self.pdf_path)
                total_pages = len(pdf_plumber_doc.pages)

                for i in range(total_pages):
                    page_num = i + 1
                    plumber_page = pdf_plumber_doc.pages[i]
                    mupdf_page = pymupdf_doc[i]
                    
                    page_data = {
                        "pdf_filename": self.pdf_path.name,
                        "pymupdf_extraction_text": mupdf_page.get_text() or "",
                        "pdfplumber_extraction_text": plumber_page.extract_text() or "",
                        "ocr_extraction_text": ""
                    }

                    # Perform OCR if image flags are set and we have libraries
                    if (self.contains_images_of_text or self.contains_images_of_nontext) and 'pytesseract' in sys.modules:
                        page_data["ocr_extraction_text"] = self._extract_ocr_for_page(mupdf_page)
                    
                    page_results.append(page_data)
                pymupdf_doc.close()
        except Exception as e:
            logger.error(f"Failed during page-by-page extraction: {e}")
            raise
        return page_results

    def _extract_ocr_for_page(self, mupdf_page: fitz.Page) -> str:
        """Extracts text from images on a single page using Tesseract OCR."""
        try:
            if not mupdf_page.get_images(full=True):
                return ""
            mat = fitz.Matrix(2.0, 2.0)
            pix = mupdf_page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            return pytesseract.image_to_string(image) or ""
        except Exception as e:
            logger.warning(f"Could not perform OCR: {e}")
            return ""

# --- HELPER FUNCTIONS ---

def clean_json_response(text: str) -> str:
    """Removes markdown formatting from JSON response."""
    cleaned = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", text, flags=re.DOTALL)
    return cleaned.strip()

def process_file_or_dir(input_path: Path, output_dir: Path):
    if input_path.is_file() and input_path.name.lower().endswith('.zip'):
        logger.info(f"Unzipping {input_path}...")
        extract_dir = output_dir / "extracted"
        extract_dir.mkdir(exist_ok=True, parents=True)
        with zipfile.ZipFile(input_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        return list(extract_dir.rglob("*.pdf"))
    elif input_path.is_dir():
        logger.info(f"Scanning directory {input_path}...")
        return list(input_path.rglob("*.pdf"))
    else:
        logger.error("Input must be a zip file or directory.")
        return []

# --- MAIN ANALYSIS TASK ---

def run_analysis(pdf_files: List[Path], output_file: Path):
    results = []
    model = genai.GenerativeModel('gemini-2.5-pro')
    
    total = len(pdf_files)
    logger.info(f"Found {total} PDF files to process.")
    
    for idx, pdf_path in enumerate(pdf_files):
        logger.info(f"[{idx+1}/{total}] Processing {pdf_path.name}...")
        try:
            # EXTRACT TEXT
            extractor = PDFTextExtractor(
                pdf_path=str(pdf_path),
                contains_tables=False,
                contains_images_of_text=False, 
                contains_images_of_nontext=False
            )
            extraction_results = extractor.extract_all_pages()
            
            full_text = ""
            for page in extraction_results:
                text = page.get("pymupdf_extraction_text", "")
                if not text.strip():
                    text = page.get("pdfplumber_extraction_text", "")
                full_text += text + "\n"
            
            chosen_bill_text = full_text.strip()

            # OCR Fallback
            if not chosen_bill_text:
                logger.info(f"  No text found, attempting OCR for {pdf_path.name}...")
                try:
                    extractor = PDFTextExtractor(
                        pdf_path=str(pdf_path),
                        contains_tables=False,
                        contains_images_of_text=True, 
                        contains_images_of_nontext=False
                    )
                    extraction_results = extractor.extract_all_pages()
                    full_text = ""
                    for page in extraction_results:
                        text = page.get("ocr_extraction_text", "")
                        if not text.strip():
                            text = page.get("pymupdf_extraction_text", "")
                        full_text += text + "\n"
                    chosen_bill_text = full_text.strip()
                except Exception as e:
                    logger.warning(f"  OCR Failed: {e}")

            if not chosen_bill_text:
                logger.warning(f"  Empty content for {pdf_path.name}")
                results.append({
                    "bill_name": pdf_path.name,
                    "error": "No text content found",
                    "committees": []
                })
                continue

            # BUILD PROMPT
            prompt = f"""
You are given a definition log of all potential committees and their descriptions
{COMMITTEES_DATA}

While making your decision use the following 4 files as rules to base your decisions on which bills should get which committees.

{FINANCE_RESP}
{GENERAL_RESP}
{HOUSE_RULES}
{LEGISLATIVE_RESP}

Follow these rules strictly for all future decisions.

using the bill name and introduction assign it committees

{chosen_bill_text}

The following is an example of the correct results, it has the bill name, introduction, and the correct committees. This should be used as an example for when you are assigning committees to bills. 

{EXAMPLES_3_SHOT}
   
Please give me a json where each entry has the bill name and your decision of which committees should be applied to that bill.

A single bill is allowed to have between 1 to 4 committees, it is not limited to or restricted to having more or less,
only apply those that make sense using the rules.

Also note that a bill discussing a constitutional amendment should be assigned to both the JHA and FIN committees, along with any other committees that make sense.

Please use this as the layout for the produced output (use the prompt style given here):
[  
      {{
          "prompt_style" : "This is the combination of one bill and three shot",
         "bill_name": "Name of bill ",
         "committees": ["committee_id 1", "committee_id 2", "committee_id 3", "committee_id 4"],
          "reasoning": "only when prompted add in text here other wise leave blank"
       }},
       {{
           "prompt_style" : "This is the combination of one bill and three shot",
           "bill_name": "Name of bill ",
           "committees": ["committee_id 1", "committee_id 2", "committee_id 3", "committee_id 4"],
           "reasoning": ""
       }}
    ]
"""
            # QUERY LLM
            response = model.generate_content(prompt)
            cleaned_json = clean_json_response(response.text)
            bill_data = json.loads(cleaned_json)

            # NORMALIZE OUTPUT
            if isinstance(bill_data, list):
                for item in bill_data:
                    item['bill_name'] = pdf_path.name
                results.extend(bill_data)
            elif isinstance(bill_data, dict):
                bill_data['bill_name'] = pdf_path.name
                results.append(bill_data)
                
            time.sleep(1) # Rate limit check
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")
            results.append({
                "bill_name": pdf_path.name,
                "error": str(e)
            })

    # SAVE RESULTS
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Finished! saved results to {output_file}")
    print(f"\nSUCCESS: Results saved to {output_file}")

# --- ENTRY POINT ---

def main():
    parser = argparse.ArgumentParser(description="RefBot - Standalone PDF Committee Analyzer")
    parser.add_argument("input", type=str, help="Path to zip file containing bill PDFs")
    parser.add_argument("--api-key", type=str, required=True, help="Google Gemini API Key")
    parser.add_argument("--output", type=str, default="refbot_results.json", help="Output JSON filename")
    
    args = parser.parse_args()
    
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    
    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)
        
    # Setup working directory (temp folder)
    work_dir = Path("refbot_work_dir")
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(exist_ok=True)
    
    try:
        pdf_files = process_file_or_dir(input_path, work_dir)
        if not pdf_files:
            print("No PDF files found to process.")
            sys.exit(0)
            
        genai.configure(api_key=args.api_key)
        
        run_analysis(pdf_files, output_path)
        
    finally:
        # Cleanup
        if work_dir.exists():
            shutil.rmtree(work_dir)

if __name__ == "__main__":
    main()
