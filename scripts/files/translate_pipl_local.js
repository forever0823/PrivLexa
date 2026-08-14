const fs = require("fs");
const path = require("path");

const ARTICLE_TRANSLATIONS = {
  1: {
    title: "Purpose of the Legislation",
    lines: [
      "This Law is enacted, in accordance with the Constitution, to protect personal information rights and interests, regulate personal information processing activities, and promote the reasonable use of personal information.",
    ],
  },
  2: {
    title: "Protection of Personal Information Rights and Interests",
    lines: [
      "The personal information of natural persons is protected by law, and no organization or individual may infringe upon the personal information rights and interests of natural persons.",
    ],
  },
  3: {
    title: "Scope and Extraterritorial Application",
    lines: [
      "This Law applies to the processing of personal information of natural persons within the territory of the People's Republic of China. This Law also applies to the processing, outside the territory of the People's Republic of China, of the personal information of natural persons within the territory of the People's Republic of China where one of the following circumstances exists: (1) the purpose is to provide products or services to natural persons within the territory; (2) to analyze or assess the conduct of natural persons within the territory; or (3) other circumstances provided by laws or administrative regulations.",
    ],
  },
  4: {
    title: "Definitions of Personal Information and Processing",
    lines: [
      "Personal information refers to all kinds of information related to identified or identifiable natural persons recorded by electronic or other means, excluding information that has been anonymized. The processing of personal information includes the collection, storage, use, processing, transmission, provision, disclosure, deletion, and similar handling of personal information.",
    ],
  },
  5: {
    title: "Principles of Lawfulness, Legitimacy, Necessity, and Good Faith",
    lines: [
      "The processing of personal information shall follow the principles of lawfulness, legitimacy, necessity, and good faith, and personal information shall not be processed through misleading, fraud, coercion, or other such means.",
    ],
  },
  6: {
    title: "Purpose Limitation and Minimum Necessity",
    lines: [
      "The processing of personal information shall have a clear and reasonable purpose and shall be directly related to the purpose of processing, and the method having the least impact on personal rights and interests shall be adopted. The collection of personal information shall be limited to the minimum scope necessary to achieve the purpose of processing, and excessive collection of personal information is prohibited.",
    ],
  },
  7: {
    title: "Principle of Openness and Transparency",
    lines: [
      "The processing of personal information shall follow the principles of openness and transparency, disclose the rules for processing personal information, and expressly indicate the purpose, method, and scope of processing.",
    ],
  },
  8: {
    title: "Principle of Information Quality",
    lines: [
      "The processing of personal information shall ensure the quality of personal information and avoid adverse effects on personal rights and interests caused by inaccurate or incomplete personal information.",
    ],
  },
  9: {
    title: "Processor Responsibility and Security Assurance",
    lines: [
      "A personal information processor shall be responsible for its personal information processing activities and shall adopt necessary measures to ensure the security of the personal information it processes.",
    ],
  },
  10: {
    title: "Prohibition of Illegal Processing",
    lines: [
      "No organization or individual may illegally collect, use, process, or transmit the personal information of others, or illegally trade in, provide, or disclose the personal information of others; nor may they engage in personal information processing activities that endanger national security or the public interest.",
    ],
  },
  11: {
    title: "National Protection System",
    lines: [
      "The State shall establish and improve the personal information protection system, prevent and punish acts infringing upon personal information rights and interests, strengthen publicity and education on personal information protection, and promote a sound environment in which the government, enterprises, relevant social organizations, and the public jointly participate in personal information protection.",
    ],
  },
  12: {
    title: "Participation in International Rules and Mutual Recognition",
    lines: [
      "The State shall actively participate in the formulation of international rules for personal information protection, promote international exchanges and cooperation in personal information protection, and advance mutual recognition of rules and standards for personal information protection with other countries, regions, and international organizations.",
    ],
  },
  13: {
    title: "Lawful Conditions for Processing Personal Information",
    lines: [
      "A personal information processor may process personal information only under one of the following circumstances:",
      "(1) the individual's consent has been obtained;",
      "(2) where necessary for the conclusion or performance of a contract to which the individual is a party, or where necessary for human resources management in accordance with lawfully formulated labor rules and regulations and lawfully concluded collective contracts;",
      "(3) where necessary for the performance of statutory duties or statutory obligations;",
      "(4) where necessary to respond to public health emergencies, or where necessary in an emergency to protect the life, health, or property safety of natural persons;",
      "(5) where personal information is processed within a reasonable scope for news reporting, public opinion supervision, or other acts for the public interest;",
      "(6) where personal information that has been disclosed by the individual or otherwise lawfully disclosed is processed within a reasonable scope in accordance with this Law;",
      "(7) where other circumstances are provided by laws or administrative regulations. Under other relevant provisions of this Law, the processing of personal information shall obtain the individual's consent, but consent is not required where any of the circumstances in items (2) to (7) of the preceding paragraph exists.",
    ],
  },
  14: {
    title: "Valid Consent and Renewed Consent",
    lines: [
      "Where personal information is processed based on the individual's consent, such consent shall be given voluntarily and explicitly by the individual on the premise of full knowledge. Where laws or administrative regulations provide that separate consent or written consent shall be obtained for processing personal information, those provisions shall prevail. Where the purpose of processing, the method of processing, or the categories of personal information processed change, the individual's consent shall be obtained again.",
    ],
  },
  15: {
    title: "Withdrawal of Consent",
    lines: [
      "Where personal information is processed based on the individual's consent, the individual has the right to withdraw that consent. A personal information processor shall provide a convenient method for withdrawing consent. Withdrawal of consent by the individual does not affect the validity of personal information processing activities that have already been carried out on the basis of consent before its withdrawal.",
    ],
  },
  16: {
    title: "No Refusal of Non-Essential Services on Grounds of Non-Consent",
    lines: [
      "A personal information processor may not refuse to provide products or services on the ground that the individual does not consent to the processing of the individual's personal information or withdraws consent; except where the processing of personal information is necessary for the provision of the products or services.",
    ],
  },
  17: {
    title: "Duty to Inform Before Processing",
    lines: [
      "Before processing personal information, a personal information processor shall truthfully, accurately, and completely inform the individual of the following matters in a conspicuous manner and in clear and easy-to-understand language:",
      "(1) the name or title and contact information of the personal information processor;",
      "(2) the purpose and method of processing personal information, as well as the categories of personal information processed and the retention period;",
      "(3) the methods and procedures for the individual to exercise the rights provided for in this Law;",
      "(4) other matters that laws and administrative regulations require to be notified. Where the matters provided in the preceding paragraph change, the changed part shall be notified to the individual. Where a personal information processor informs the matters provided in paragraph 1 by formulating personal information processing rules, such rules shall be disclosed and easy to consult and preserve.",
    ],
  },
  18: {
    title: "Exceptions to Notice and Subsequent Notice",
    lines: [
      "Where a personal information processor processes personal information under circumstances where laws or administrative regulations provide that confidentiality shall be maintained or that no notice is required, it may refrain from notifying the individual of the matters provided in paragraph 1 of the preceding article. Where, in an emergency, it is impossible to notify the individual in a timely manner for the protection of the life, health, or property safety of natural persons, the personal information processor shall notify the individual promptly after the emergency has been eliminated.",
    ],
  },
  19: {
    title: "Minimum Retention Period",
    lines: [
      "Except as otherwise provided by laws or administrative regulations, the retention period of personal information shall be the shortest time necessary to achieve the purpose of processing.",
    ],
  },
  20: {
    title: "Joint Processing Liability",
    lines: [
      "Where two or more personal information processors jointly determine the purpose and method of processing personal information, they shall agree on their respective rights and obligations. However, such agreement does not affect an individual's right to request any one of those personal information processors to exercise the rights provided for in this Law. Where personal information is jointly processed by personal information processors and damage is caused by infringement of personal information rights and interests, they shall bear joint and several liability in accordance with law.",
    ],
  },
  21: {
    title: "Entrusted Processing and Supervision of Entrusted Parties",
    lines: [
      "Where a personal information processor entrusts the processing of personal information to an entrusted party, it shall agree with the entrusted party on the purpose, duration, method of entrusted processing, the categories of personal information, protective measures, and the rights and obligations of both parties, among other matters, and shall supervise the personal information processing activities of the entrusted party. The entrusted party shall process personal information in accordance with the agreement and shall not process personal information beyond the agreed purpose or method of processing, among other agreed matters; if the entrusted contract does not take effect, is invalid, is revoked, or is terminated, the entrusted party shall return the personal information to the personal information processor or delete it and shall not retain it. Without the consent of the personal information processor, the entrusted party may not re-entrust another person to process personal information.",
    ],
  },
  22: {
    title: "Transfer of Personal Information Due to Organizational Changes",
    lines: [
      "Where a personal information processor needs to transfer personal information due to merger, division, dissolution, declared bankruptcy, or other reasons, it shall notify the individual of the name or title and contact information of the recipient. The recipient shall continue to perform the obligations of the personal information processor. Where the recipient changes the original purpose or method of processing, the individual's consent shall be obtained again in accordance with this Law.",
    ],
  },
  23: {
    title: "Provision of Personal Information to Other Processors",
    lines: [
      "Where a personal information processor provides the personal information it processes to another personal information processor, it shall notify the individual of the recipient's name or title, contact information, purpose of processing, method of processing, and categories of personal information, and shall obtain the individual's separate consent. The recipient shall process personal information within the scope of the above-mentioned purpose of processing, method of processing, and categories of personal information. Where the recipient changes the original purpose or method of processing, the individual's consent shall be obtained again in accordance with this Law.",
    ],
  },
  24: {
    title: "Rules for Automated Decision-Making",
    lines: [
      "Where a personal information processor uses personal information for automated decision-making, it shall ensure the transparency of the decision-making and the fairness and impartiality of the results, and may not impose unreasonable differential treatment on individuals in transaction prices or other transaction conditions. Where information push or commercial marketing is carried out toward individuals through automated decision-making, options not directed at their personal characteristics shall be provided at the same time, or a convenient method of refusal shall be provided to the individual. Where a decision that has a major impact on an individual's rights and interests is made through automated decision-making, the individual has the right to require the personal information processor to provide an explanation and has the right to refuse a decision made solely through automated decision-making.",
    ],
  },
  25: {
    title: "Restrictions on Making Personal Information Public",
    lines: [
      "A personal information processor may not make the personal information it processes public, except where the individual's separate consent has been obtained.",
    ],
  },
  26: {
    title: "Images and Identification in Public Places",
    lines: [
      "The installation of image collection and personal identification equipment in public places shall be necessary for maintaining public security, shall comply with relevant State provisions, and shall be accompanied by conspicuous warning signs. The personal images and identification information collected may be used only for the purpose of maintaining public security and may not be used for any other purpose; except where the individual's separate consent has been obtained.",
    ],
  },
  27: {
    title: "Processing of Publicly Disclosed Personal Information",
    lines: [
      "A personal information processor may process personal information disclosed by the individual or other lawfully disclosed personal information within a reasonable scope; except where the individual expressly refuses. Where a personal information processor processes disclosed personal information and has a major impact on the individual's rights and interests, the individual's consent shall be obtained in accordance with this Law.",
    ],
  },
  28: {
    title: "Definition of Sensitive Personal Information and Conditions for Processing",
    lines: [
      "Sensitive personal information refers to personal information that, once leaked or illegally used, is likely to cause harm to the personal dignity of natural persons or endanger personal or property safety, including biometric data, religious belief, specific identity, medical and health information, financial accounts, whereabouts and tracks, and other information, as well as the personal information of minors under the age of fourteen. A personal information processor may process sensitive personal information only where there is a specific purpose and sufficient necessity, and strict protective measures are taken.",
    ],
  },
  29: {
    title: "Separate Consent for Sensitive Personal Information",
    lines: [
      "The processing of sensitive personal information shall obtain the individual's separate consent; where laws or administrative regulations provide that written consent shall be obtained for the processing of sensitive personal information, those provisions shall prevail.",
    ],
  },
  30: {
    title: "Special Notice for Sensitive Personal Information",
    lines: [
      "Where a personal information processor processes sensitive personal information, in addition to the matters provided in paragraph 1 of Article 17 of this Law, it shall also notify the individual of the necessity of processing sensitive personal information and the impact on the individual's rights and interests; except where, in accordance with this Law, the individual need not be notified.",
    ],
  },
  31: {
    title: "Personal Information of Minors Under Fourteen",
    lines: [
      "Where a personal information processor processes the personal information of a minor under the age of fourteen, it shall obtain the consent of the minor's parents or other guardians. Where a personal information processor processes the personal information of a minor under the age of fourteen, it shall formulate special rules for processing personal information.",
    ],
  },
  32: {
    title: "Special Permits or Restrictions for Processing Sensitive Information",
    lines: [
      "Where laws or administrative regulations provide that the processing of sensitive personal information shall obtain relevant administrative permission or be subject to other restrictions, those provisions shall prevail.",
    ],
  },
  33: {
    title: "Rules Applicable to State Organs",
    lines: [
      "This Law applies to the activities of State organs in processing personal information; where this Section contains special provisions, those provisions shall apply.",
    ],
  },
  34: {
    title: "Limits on Processing by State Organs",
    lines: [
      "Where a State organ processes personal information for the performance of statutory duties, it shall do so in accordance with the authority and procedures provided by laws and administrative regulations and may not exceed the scope and limits necessary for the performance of its statutory duties.",
    ],
  },
  35: {
    title: "Exceptions to Notice Obligations for State Organs",
    lines: [
      "Where a State organ processes personal information for the performance of statutory duties, it shall perform the duty to inform in accordance with this Law; except where the circumstances provided in paragraph 1 of Article 18 of this Law exist, or where informing would impede the State organ's performance of its statutory duties.",
    ],
  },
  36: {
    title: "Domestic Storage and Cross-Border Assessment for State Organs",
    lines: [
      "Personal information processed by State organs shall be stored within the territory of the People's Republic of China; where it is truly necessary to provide it abroad, a security assessment shall be conducted. Relevant departments may be requested to provide support and assistance for the security assessment.",
    ],
  },
  37: {
    title: "Application to Authorized Public Affairs Organizations",
    lines: [
      "Where organizations authorized by laws or regulations to manage public affairs process personal information for the performance of statutory duties, the provisions of this Law on State organs processing personal information shall apply.",
    ],
  },
  38: {
    title: "Conditions for Cross-Border Transfer of Personal Information",
    lines: [
      "Where a personal information processor truly needs to provide personal information outside the territory of the People's Republic of China for business or other needs, one of the following conditions shall be met:",
      "(1) passing the security assessment organized by the national cyberspace administration authority in accordance with Article 40 of this Law;",
      "(2) obtaining personal information protection certification from a professional institution in accordance with the provisions of the national cyberspace administration authority;",
      "(3) entering into a contract with the overseas recipient in accordance with the standard contract formulated by the national cyberspace administration authority, stipulating the rights and obligations of both parties;",
      "(4) other conditions provided by laws, administrative regulations, or the national cyberspace administration authority.",
      "Where international treaties or agreements concluded or participated in by the People's Republic of China contain provisions on the conditions for providing personal information outside the territory of the People's Republic of China and similar matters, those provisions may be followed. A personal information processor shall take necessary measures to ensure that the personal information processing activities of the overseas recipient meet the personal information protection standards prescribed by this Law.",
    ],
  },
  39: {
    title: "Separate Consent and Notice for Cross-Border Transfer",
    lines: [
      "Where a personal information processor provides personal information outside the territory of the People's Republic of China, it shall notify the individual of matters such as the name or title of the overseas recipient, contact information, purpose of processing, method of processing, categories of personal information, and the methods and procedures for the individual to exercise the rights provided in this Law against the overseas recipient, and shall obtain the individual's separate consent.",
    ],
  },
  40: {
    title: "Domestic Storage for Critical Information Infrastructure and Large-Scale Processors",
    lines: [
      "Critical information infrastructure operators and personal information processors whose processing of personal information reaches the quantity prescribed by the national cyberspace administration authority shall store within the territory the personal information collected and generated within the territory of the People's Republic of China. Where it is truly necessary to provide such information abroad, they shall pass the security assessment organized by the national cyberspace administration authority; where laws, administrative regulations, or the national cyberspace administration authority provide that a security assessment need not be conducted, those provisions shall prevail.",
    ],
  },
  41: {
    title: "Approval for Foreign Judicial or Law Enforcement Requests",
    lines: [
      "The competent authorities of the People's Republic of China shall handle requests from foreign judicial or law enforcement bodies for the provision of personal information stored within the territory in accordance with relevant laws, and international treaties or agreements concluded or participated in by the People's Republic of China, or in accordance with the principle of equality and reciprocity. Without the approval of the competent authorities of the People's Republic of China, personal information processors may not provide personal information stored within the territory of the People's Republic of China to foreign judicial or law enforcement bodies.",
    ],
  },
  42: {
    title: "Restrictive List for Overseas Infringing Entities",
    lines: [
      "Where overseas organizations or individuals engage in personal information processing activities that infringe upon the personal information rights and interests of citizens of the People's Republic of China, or endanger the national security or public interest of the People's Republic of China, the national cyberspace administration authority may place them on a list restricting or prohibiting the provision of personal information to them, announce such list, and take measures such as restricting or prohibiting the provision of personal information to them.",
    ],
  },
  43: {
    title: "Reciprocal Countermeasures",
    lines: [
      "Where any country or region takes discriminatory prohibitions, restrictions, or other similar measures against the People's Republic of China in terms of personal information protection, the People's Republic of China may take reciprocal measures against that country or region based on actual circumstances.",
    ],
  },
  44: {
    title: "The Individual's Right to Know, Decide, and Refuse",
    lines: [
      "Individuals enjoy the right to know and the right to decide regarding the processing of their personal information, and have the right to restrict or refuse others from processing their personal information; except as otherwise provided by laws or administrative regulations.",
    ],
  },
  45: {
    title: "Rights to Access, Copy, and Transfer",
    lines: [
      "Individuals have the right to consult and copy their personal information from personal information processors; except where the circumstances provided in paragraph 1 of Article 18 and Article 35 of this Law exist. Where an individual requests to consult or copy his or her personal information, the personal information processor shall provide it in a timely manner. Where an individual requests the transfer of personal information to a personal information processor designated by the individual and the conditions prescribed by the national cyberspace administration authority are met, the personal information processor shall provide a means for such transfer.",
    ],
  },
  46: {
    title: "Right to Rectification and Supplementation",
    lines: [
      "Where an individual finds that his or her personal information is inaccurate or incomplete, the individual has the right to request a personal information processor to make corrections or supplements. Where an individual requests the correction or supplementation of his or her personal information, the personal information processor shall verify the relevant personal information and make corrections or supplements in a timely manner.",
    ],
  },
  47: {
    title: "Right to Deletion",
    lines: [
      "Under any of the following circumstances, a personal information processor shall take the initiative to delete personal information; where the personal information processor has not deleted it, the individual has the right to request deletion: (1) the purpose of processing has been achieved, cannot be achieved, or the personal information is no longer necessary for achieving the purpose of processing; (2) the personal information processor stops providing products or services, or the retention period has expired; (3) the individual withdraws consent; (4) the personal information processor processes personal information in violation of laws, administrative regulations, or agreements; or (5) other circumstances provided by laws or administrative regulations. Where the retention period prescribed by laws or administrative regulations has not expired, or where deleting personal information is technically difficult to achieve, the personal information processor shall stop processing other than storing the personal information and taking necessary security protection measures.",
    ],
  },
  48: {
    title: "Right to Require Explanations of the Rules",
    lines: [
      "Individuals have the right to require a personal information processor to explain its rules for processing personal information.",
    ],
  },
  49: {
    title: "Rights of Close Relatives Regarding the Deceased's Information",
    lines: [
      "Where a natural person dies, the person's close relatives, for their own lawful and legitimate interests, may exercise the rights provided in this Chapter to consult, copy, correct, and delete the deceased's relevant personal information, among other rights; except where the deceased made other arrangements before death.",
    ],
  },
  50: {
    title: "Mechanisms for Rights Requests and Litigation",
    lines: [
      "A personal information processor shall establish a convenient mechanism for accepting and handling applications by individuals to exercise their rights. Where a request by an individual to exercise rights is refused, the reasons shall be explained. Where a personal information processor refuses an individual's request to exercise rights, the individual may file a lawsuit in the People's Court in accordance with law.",
    ],
  },
  51: {
    title: "Security Protection Measures",
    lines: [
      "A personal information processor shall, according to the purpose and method of processing personal information, the categories of personal information, the impact on personal rights and interests, possible security risks, and other such factors, take the following measures to ensure that personal information processing activities comply with laws and administrative regulations and to prevent unauthorized access to, and the leakage, tampering, or loss of, personal information: (1) formulating internal management systems and operating procedures; (2) implementing classified management of personal information; (3) taking corresponding security technical measures such as encryption and de-identification; (4) reasonably determining operating permissions for personal information processing, and regularly conducting security education and training for employees; (5) formulating and organizing the implementation of emergency response plans for personal information security incidents; (6) other measures provided by laws and administrative regulations.",
    ],
  },
  52: {
    title: "Person in Charge of Personal Information Protection",
    lines: [
      "A personal information processor whose processing of personal information reaches the quantity prescribed by the national cyberspace administration authority shall designate a person in charge of personal information protection, who shall be responsible for supervising personal information processing activities and the protective measures adopted, among other matters. A personal information processor shall disclose the contact information of the person in charge of personal information protection, and submit the name and contact information of that person and other such information to the departments performing personal information protection duties.",
    ],
  },
  53: {
    title: "Domestic Entity or Representative of Overseas Processors",
    lines: [
      "A personal information processor outside the territory of the People's Republic of China as provided in paragraph 2 of Article 3 of this Law shall establish a specialized entity or designate a representative within the territory of the People's Republic of China to be responsible for matters related to personal information protection, and shall submit the name of the relevant entity or the name and contact information of the representative, and other such information, to the departments performing personal information protection duties.",
    ],
  },
  54: {
    title: "Periodic Compliance Audit",
    lines: [
      "A personal information processor shall periodically conduct compliance audits of its processing of personal information to determine whether it complies with laws and administrative regulations.",
    ],
  },
  55: {
    title: "Triggers for Personal Information Protection Impact Assessments",
    lines: [
      "Under any of the following circumstances, a personal information processor shall conduct a personal information protection impact assessment in advance and keep a record of the processing: (1) processing sensitive personal information; (2) using personal information for automated decision-making; (3) entrusting the processing of personal information, providing personal information to other personal information processors, or making personal information public; (4) providing personal information outside the territory; (5) other personal information processing activities that have a major impact on personal rights and interests.",
    ],
  },
  56: {
    title: "Contents and Retention of Impact Assessments",
    lines: [
      "A personal information protection impact assessment shall include the following: (1) whether the purpose and method of processing personal information, and similar matters, are lawful, legitimate, and necessary; (2) the impact on personal rights and interests and the security risks; (3) whether the protective measures taken are lawful, effective, and appropriate to the degree of risk. Reports on personal information protection impact assessments and records of processing shall be retained for at least three years.",
    ],
  },
  57: {
    title: "Remedial Measures and Notice for Security Incidents",
    lines: [
      "Where personal information is leaked, tampered with, or lost, or where such events may occur, the personal information processor shall immediately take remedial measures and notify the departments performing personal information protection duties and the individuals concerned. The notice shall include the following matters: (1) the categories of information leaked, tampered with, or lost, or likely to be leaked, tampered with, or lost, the causes, and the possible harm; (2) the remedial measures taken by the personal information processor and the measures that individuals may take to mitigate the harm; (3) the contact information of the personal information processor. Where the measures taken by the personal information processor can effectively avoid harm caused by the leakage, tampering, or loss of information, the personal information processor may refrain from notifying individuals; if the departments performing personal information protection duties consider that harm may be caused, they have the right to require the personal information processor to notify individuals.",
    ],
  },
  58: {
    title: "Special Obligations of Important Internet Platform Operators",
    lines: [
      "Personal information processors that provide important internet platform services, have a huge number of users, and have complex business types shall perform the following obligations:",
      "(1) establish and improve a personal information protection compliance system in accordance with State provisions, and establish an independent body composed mainly of external members to supervise personal information protection;",
      "(2) follow the principles of openness, fairness, and impartiality, formulate platform rules, and clarify the standards for platform-based product or service providers to process personal information and their obligations to protect personal information;",
      "(3) stop providing services to platform-based product or service providers that seriously violate laws or administrative regulations in processing personal information;",
      "(4) regularly issue social responsibility reports on personal information protection and accept public supervision.",
    ],
  },
  59: {
    title: "Security Assurance and Assistance Obligations of Entrusted Parties",
    lines: [
      "An entrusted party that accepts entrusted processing of personal information shall, in accordance with this Law and relevant laws and administrative regulations, take necessary measures to ensure the security of the personal information processed, and assist the personal information processor in performing the obligations provided for in this Law.",
    ],
  },
  60: {
    title: "Structure of Supervisory Authorities",
    lines: [
      "The national cyberspace administration authority is responsible for overall coordination of personal information protection work and related supervision and administration work. Relevant departments of the State Council shall, in accordance with this Law and relevant laws and administrative regulations, be responsible for personal information protection and supervision and administration work within the scope of their respective duties. The duties of relevant departments of local people's governments at or above the county level for personal information protection and supervision and administration shall be determined in accordance with relevant State provisions. The departments provided in the preceding two paragraphs are collectively referred to as the departments performing personal information protection duties.",
    ],
  },
  61: {
    title: "Duties of Supervisory Authorities",
    lines: [
      "The departments performing personal information protection duties shall perform the following personal information protection duties:",
      "(1) conduct publicity and education on personal information protection, and guide and supervise personal information processors in carrying out personal information protection work;",
      "(2) accept and handle complaints and reports related to personal information protection;",
      "(3) organize assessments of personal information protection in applications and similar products, and publish the assessment results;",
      "(4) investigate and handle illegal personal information processing activities;",
      "(5) other duties provided by laws and administrative regulations.",
    ],
  },
  62: {
    title: "Work Advanced by the National Cyberspace Administration Authority",
    lines: [
      "The national cyberspace administration authority shall coordinate relevant departments in advancing the following personal information protection work under this Law:",
      "(1) formulate specific rules and standards for personal information protection;",
      "(2) formulate special rules and standards for personal information protection for small personal information processors, for the processing of sensitive personal information, and for new technologies and applications such as facial recognition and artificial intelligence;",
      "(3) support the research, development, and promotion of secure and convenient electronic identity authentication technology, and advance the construction of public network identity authentication services;",
      "(4) advance the development of a socialized service system for personal information protection, and support relevant institutions in carrying out personal information protection assessment and certification services;",
      "(5) improve the mechanisms for complaints and reports concerning personal information protection.",
    ],
  },
  63: {
    title: "Investigative Measures of Supervisory Authorities",
    lines: [
      "The departments performing personal information protection duties may, in performing such duties, take the following measures: (1) question relevant parties and investigate matters related to personal information processing activities; (2) consult and copy contracts, records, account books, and other relevant materials of the parties related to personal information processing activities; (3) conduct on-site inspections and investigate suspected illegal personal information processing activities; (4) inspect equipment and articles related to personal information processing activities; where there is evidence proving that such equipment or articles are used for illegal personal information processing activities, and upon written report to and approval by the principal person in charge of the department, they may be sealed up or seized. When the departments performing personal information protection duties perform their duties in accordance with law, the parties concerned shall provide assistance and cooperate, and may not refuse or obstruct.",
    ],
  },
  64: {
    title: "Risk Interviews and Rectification",
    lines: [
      "Where the departments performing personal information protection duties discover, in the course of performing their duties, that personal information processing activities involve relatively high risks or that a personal information security incident has occurred, they may, in accordance with prescribed authority and procedures, interview the legal representative or principal person in charge of the personal information processor, or require the personal information processor to entrust a professional institution to conduct a compliance audit of its personal information processing activities. The personal information processor shall take measures as required, make rectifications, and eliminate hidden risks. Where the departments performing personal information protection duties discover in the course of performing their duties that illegal processing of personal information is suspected of constituting a crime, they shall promptly transfer the case to the public security organ for handling in accordance with law.",
    ],
  },
  65: {
    title: "Complaints, Reports, and Publication of Contact Information",
    lines: [
      "Any organization or individual has the right to file complaints or reports with the departments performing personal information protection duties concerning illegal personal information processing activities. The departments receiving complaints or reports shall handle them in a timely manner in accordance with law and shall inform the complainants or reporters of the handling results. The departments performing personal information protection duties shall publish the contact information for receiving complaints and reports.",
    ],
  },
  66: {
    title: "General Violations and Heavy Fines",
    lines: [
      "Where personal information is processed in violation of this Law, or where personal information is processed without fulfilling the personal information protection obligations provided in this Law, the departments performing personal information protection duties shall order corrections, give a warning, confiscate unlawful gains, and order the suspension or termination of services for applications that unlawfully process personal information; where corrections are refused, a fine of not more than RMB 1 million shall also be imposed; the directly responsible person in charge and other directly responsible personnel shall be fined not less than RMB 10,000 but not more than RMB 100,000. Where the unlawful act provided in the preceding paragraph is serious, the departments performing personal information protection duties at or above the provincial level shall order corrections, confiscate unlawful gains, and impose a fine of not more than RMB 50 million or not more than 5 percent of the preceding year's turnover, and may also order suspension of the relevant business or suspension of operations for rectification and notify the relevant competent authorities to revoke the relevant business permits or business license; the directly responsible person in charge and other directly responsible personnel shall be fined not less than RMB 100,000 but not more than RMB 1 million, and may also be prohibited from serving as directors, supervisors, senior management personnel, or persons in charge of personal information protection of the relevant enterprise for a certain period.",
    ],
  },
  67: {
    title: "Entry into Credit Records and Public Disclosure",
    lines: [
      "Where an unlawful act provided in this Law occurs, it shall be recorded in the credit file in accordance with relevant laws and administrative regulations and be publicly disclosed.",
    ],
  },
  68: {
    title: "Liability of State Organs for Violations",
    lines: [
      "Where a State organ fails to perform the personal information protection obligations provided in this Law, its superior authority or the departments performing personal information protection duties shall order corrections; the directly responsible person in charge and other directly responsible personnel shall be sanctioned in accordance with law. Where staff members of the departments performing personal information protection duties neglect their duties, abuse their powers, or engage in malpractice for personal gain, and the conduct does not constitute a crime, they shall be sanctioned in accordance with law.",
    ],
  },
  69: {
    title: "Reversed Burden of Proof for Infringement Compensation",
    lines: [
      "Where the processing of personal information infringes upon personal information rights and interests and causes damage, and the personal information processor cannot prove that it is not at fault, the personal information processor shall bear tort liability such as compensation for damages. The compensation for damages provided in the preceding paragraph shall be determined according to the loss suffered by the individual or the benefits obtained by the personal information processor as a result; where the loss suffered by the individual and the benefits obtained by the personal information processor are difficult to determine, the amount of compensation shall be determined based on the actual circumstances.",
    ],
  },
  70: {
    title: "Public Interest Litigation",
    lines: [
      "Where a personal information processor processes personal information in violation of this Law and infringes upon the rights and interests of numerous individuals, the People's Procuratorate, consumer organizations prescribed by law, and organizations designated by the national cyberspace administration authority may file a lawsuit with the People's Court in accordance with law.",
    ],
  },
  71: {
    title: "Public Security Penalties and Criminal Liability",
    lines: [
      "Where a violation of this Law constitutes a violation of public security administration, public security administration penalties shall be imposed in accordance with law; where a crime is constituted, criminal liability shall be pursued in accordance with law.",
    ],
  },
  72: {
    title: "Personal and Household Affairs Exception and Application of Special Laws",
    lines: [
      "This Law does not apply where a natural person processes personal information for personal or family affairs. Where laws contain provisions on the processing of personal information in statistical or archives management activities organized and implemented by people's governments at all levels and their relevant departments, those provisions shall apply.",
    ],
  },
  73: {
    title: "Definitions of Terms",
    lines: [
      "For the purposes of this Law, the following terms have the meanings set out below:",
      "(1) \"personal information processor\" means an organization or individual that independently determines the purpose and method of processing in personal information processing activities.",
      "(2) \"automated decision-making\" means the activities of automatically analyzing or assessing an individual's behavioral habits, interests, or economic, health, and credit status, and making decisions, through computer programs.",
      "(3) \"de-identification\" means the process by which personal information is processed so that specific natural persons cannot be identified without the aid of additional information.",
      "(4) \"anonymization\" means the process by which personal information is processed so that specific natural persons cannot be identified and cannot be restored.",
    ],
  },
  74: {
    title: "Effective Date",
    lines: [
      "This Law shall enter into force on November 1, 2021.",
    ],
  },
};

function parseArgs(argv) {
  const args = {
    input: path.resolve("output", "normalized", "PIPL_normalized.json"),
    output: path.resolve("output", "normalized", "PIPL_normalized.json"),
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--input" && argv[i + 1]) {
      args.input = path.resolve(argv[i + 1]);
      i += 1;
      continue;
    }
    if (arg === "--output" && argv[i + 1]) {
      args.output = path.resolve(argv[i + 1]);
      i += 1;
      continue;
    }
  }

  return args;
}

function splitChineseSentences(text) {
  return text
    .split(/(?<=[。；])/u)
    .map((part) => part.trim().replace(/[。；？]$/u, ""))
    .filter(Boolean);
}

function splitEnglishSentences(text) {
  return text
    .split(/(?<=[.;])/)
    .map((part) => part.trim().replace(/[.;]$/, ""))
    .filter(Boolean);
}

function isContextualStem(text) {
  const normalized = text.trim();
  return normalized.endsWith("：") || normalized.includes("下列") || normalized.endsWith("如下");
}

function stripEnItemPrefix(rawLine) {
  return rawLine.replace(/^\(\d+\)\s*/, "").trim();
}

function buildSourceReference(articleNumber, itemCode) {
  if (!itemCode) {
    return `第${articleNumber}条`;
  }
  return `第${articleNumber}条（${itemCode}）`;
}

function pairSegments(articleNumber, reference, zhText, enText) {
  const zhSegments = splitChineseSentences(zhText);
  const enSegments = splitEnglishSentences(enText);
  if (zhSegments.length !== enSegments.length) {
    throw new Error(
      [
        `Segment count mismatch at Article ${articleNumber}, ${reference}.`,
        `Chinese (${zhSegments.length}): ${JSON.stringify(zhSegments, null, 2)}`,
        `English (${enSegments.length}): ${JSON.stringify(enSegments, null, 2)}`,
      ].join("\n"),
    );
  }

  return zhSegments.map((zh, index) => ({
    reference,
    zh,
    en: enSegments[index],
  }));
}

function buildCandidateMap(clause, translation) {
  const candidates = new Map();
  let rawIndex = 0;

  for (const paragraph of clause.paragraphs) {
    let leadTranslation = "";

    if (paragraph.lead_text) {
      leadTranslation = translation.lines[rawIndex];
      rawIndex += 1;
      for (const segment of pairSegments(
        clause.article_number,
        buildSourceReference(clause.article_number, null),
        paragraph.lead_text,
        leadTranslation,
      )) {
        candidates.set(`${segment.reference}||${segment.zh}`, segment.en);
      }
    }

    for (const item of paragraph.items) {
      const rawItemTranslation = translation.lines[rawIndex];
      rawIndex += 1;
      const itemTranslation = stripEnItemPrefix(rawItemTranslation);
      const chineseCandidate =
        paragraph.lead_text && isContextualStem(paragraph.lead_text)
          ? `${paragraph.lead_text.replace(/[：；]$/u, "").trim()} ${item.text}`
          : item.text;
      const englishLead =
        paragraph.lead_text && isContextualStem(paragraph.lead_text)
          ? leadTranslation.trim().endsWith(":")
            ? leadTranslation.trim()
            : leadTranslation.replace(/;$/, "").trim()
          : "";
      const englishCandidate =
        paragraph.lead_text && isContextualStem(paragraph.lead_text)
          ? `${englishLead} ${itemTranslation}`
          : itemTranslation;

      for (const segment of pairSegments(
        clause.article_number,
        buildSourceReference(clause.article_number, item.item_code),
        chineseCandidate,
        englishCandidate,
      )) {
        candidates.set(`${segment.reference}||${segment.zh}`, segment.en);
      }
    }
  }

  if (rawIndex !== translation.lines.length) {
    throw new Error(
      `Article ${clause.article_number} consumed ${rawIndex} translated lines but has ${translation.lines.length}.`,
    );
  }

  return candidates;
}

function updateSummaryTitles(data) {
  if (!data.summary || !Array.isArray(data.summary.key_clauses)) {
    return;
  }

  const titleMap = new Map(
    data.clauses.map((clause) => [clause.title?.zh, clause.title?.en]).filter(([zh, en]) => zh && en),
  );

  for (const keyClause of data.summary.key_clauses) {
    if (keyClause.title && keyClause.title.zh && titleMap.has(keyClause.title.zh)) {
      keyClause.title.en = titleMap.get(keyClause.title.zh);
    }
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const data = JSON.parse(fs.readFileSync(args.input, "utf8"));

  for (const clause of data.clauses) {
    const translation = ARTICLE_TRANSLATIONS[clause.article_number];
    if (!translation) {
      throw new Error(`Missing translation for Article ${clause.article_number}.`);
    }
    if (translation.lines.length !== clause.raw_body_lines.length) {
      throw new Error(
        `Article ${clause.article_number} expects ${clause.raw_body_lines.length} lines but has ${translation.lines.length}.`,
      );
    }

    clause.title = { ...clause.title, en: translation.title };
    clause.text_en = translation.lines.join("\n");
    clause.text_en_source = "llm_generated";
  }

  const obligationLookup = new Map();
  for (const clause of data.clauses) {
    const translation = ARTICLE_TRANSLATIONS[clause.article_number];
    const candidates = buildCandidateMap(clause, translation);
    for (const [key, value] of candidates.entries()) {
      obligationLookup.set(`${clause.clause_id}||${key}`, value);
    }
  }

  for (const obligation of data.obligations) {
    const key = `${obligation.clause_id}||${obligation.source_reference}||${obligation.statement}`;
    const statementEn = obligationLookup.get(key);
    if (!statementEn) {
      throw new Error(`Missing obligation translation for ${obligation.obligation_id}.`);
    }
    obligation.statement_en = statementEn;
    obligation.statement_en_source = "llm_generated";
  }

  updateSummaryTitles(data);

  if (data.meta) {
    data.meta.pending_translations = "none";
  }

  fs.writeFileSync(args.output, JSON.stringify(data, null, 2), "utf8");

  const pendingClauseTexts = data.clauses.filter((clause) => clause.text_en_source === "pending").length;
  const pendingObligations = data.obligations.filter(
    (obligation) => obligation.statement_en_source === "pending",
  ).length;
  const pendingTitles = data.clauses.filter((clause) => !clause.title?.en).length;

  console.log(
    JSON.stringify(
      {
        output: args.output,
        clauses: data.clauses.length,
        obligations: data.obligations.length,
        pendingClauseTexts,
        pendingObligations,
        pendingTitles,
      },
      null,
      2,
    ),
  );
}

main();
