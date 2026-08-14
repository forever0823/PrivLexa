#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const ROOT_DIR = path.resolve(__dirname, "..", "..");
const NORMALIZED_DIR = path.join(ROOT_DIR, "output", "normalized");

const FILES = {
  pipl: path.join(NORMALIZED_DIR, "PIPL_normalized.json"),
  gdpr: path.join(NORMALIZED_DIR, "GDPR_normalized.json"),
  ccpa: path.join(NORMALIZED_DIR, "CCPA_normalized.json"),
  unified: path.join(NORMALIZED_DIR, "unified_knowledge_graph.json"),
  report: path.join(NORMALIZED_DIR, "kg_optimization_report.json"),
};

const PIPL_CHAPTER_TITLE_EN = {
  "总则": "General Provisions",
  "个人信息处理规则": "Rules for Processing Personal Information",
  "个人信息跨境提供的规则": "Rules for Cross-Border Provision of Personal Information",
  "个人在个人信息处理活动中的权利": "Rights of Individuals in Personal Information Processing Activities",
  "个人信息处理者的义务": "Obligations of Personal Information Processors",
  "履行个人信息保护职责的部门": "Departments Performing Personal Information Protection Duties",
  "法律责任": "Legal Liability",
  "附则": "Supplementary Provisions",
};

const PIPL_SECTION_TITLE_EN = {
  "一般规定": "General Rules",
  "敏感个人信息的处理规则": "Rules for Processing Sensitive Personal Information",
  "国家机关处理个人信息的特别规定": "Special Provisions for State Organs Processing Personal Information",
};

const DEFAULT_VOCABULARY = {
  obligation_types: {
    duty: { zh: "义务", en: "Duty" },
    right: { zh: "权利", en: "Right" },
    prohibition: { zh: "禁止", en: "Prohibition" },
    power: { zh: "授权", en: "Power" },
    permission: { zh: "许可", en: "Permission" },
    obligation: { zh: "义务", en: "Obligation" },
  },
  actors: {
    controller: { zh: "个人信息处理者", en: "Controller" },
    processor: { zh: "受托处理者", en: "Processor" },
    data_subject: { zh: "个人", en: "Data Subject" },
    supervisory_authority: { zh: "监管机构", en: "Supervisory Authority" },
    third_party: { zh: "第三方", en: "Third Party" },
    recipient: { zh: "接收方", en: "Recipient" },
    business: { zh: "企业", en: "Business" },
    service_provider: { zh: "服务提供者", en: "Service Provider" },
    consumer: { zh: "消费者", en: "Consumer" },
  },
  categories: {
    lawful_basis: { zh: "合法性基础", en: "Lawful Basis" },
    transparency: { zh: "透明度", en: "Transparency" },
    data_subject_rights: { zh: "个人权利", en: "Data Subject Rights" },
    security: { zh: "安全保障", en: "Security" },
    cross_border: { zh: "跨境传输", en: "Cross-border Transfer" },
    consent: { zh: "同意", en: "Consent" },
    accountability: { zh: "问责制", en: "Accountability" },
    data_minimization: { zh: "数据最小化", en: "Data Minimization" },
    purpose_limitation: { zh: "目的限制", en: "Purpose Limitation" },
    storage_limitation: { zh: "存储限制", en: "Storage Limitation" },
    sensitive_data: { zh: "敏感个人信息", en: "Sensitive Data" },
    enforcement: { zh: "执法与处罚", en: "Enforcement" },
    governance: { zh: "治理", en: "Governance" },
    notification: { zh: "通知义务", en: "Notification" },
    general: { zh: "一般规定", en: "General Provisions" },
  },
  jurisdictions: {
    CN: { zh: "中国", en: "China" },
    EU: { zh: "欧盟", en: "European Union" },
    US: { zh: "美国（加利福尼亚州）", en: "United States (California)" },
  },
};

const OBLIGATION_TYPE_LABELS = {
  condition: { zh: "条件", en: "Condition" },
  duty: { zh: "义务", en: "Duty" },
  exception: { zh: "例外", en: "Exception" },
  power: { zh: "授权", en: "Power" },
  prohibition: { zh: "禁止", en: "Prohibition" },
  right: { zh: "权利", en: "Right" },
};

const ACTOR_LABELS = {
  agency_board: { zh: "机构董事会", en: "Agency Board" },
  attorney_general: { zh: "总检察长", en: "Attorney General" },
  board: { zh: "欧洲数据保护委员会", en: "European Data Protection Board" },
  business: { zh: "企业", en: "Business" },
  cac: { zh: "国家网信部门", en: "Cyberspace Administration Authority" },
  california_privacy_protection_agency: { zh: "加州隐私保护局", en: "California Privacy Protection Agency" },
  close_relative: { zh: "近亲属", en: "Close Relative" },
  commission: { zh: "欧盟委员会", en: "Commission" },
  competent_department: { zh: "主管部门", en: "Competent Department" },
  consumer: { zh: "消费者", en: "Consumer" },
  contractor: { zh: "承包商", en: "Contractor" },
  controller: { zh: "控制者", en: "Controller" },
  controller_and_processor: { zh: "控制者和处理者", en: "Controller and Processor" },
  controller_or_processor: { zh: "控制者或处理者", en: "Controller or Processor" },
  court: { zh: "法院", en: "Court" },
  data_subject: { zh: "个人", en: "Data Subject" },
  general: { zh: "一般主体", en: "General Actor" },
  individual: { zh: "个人", en: "Individual" },
  individual_processor_or_org: { zh: "个人处理者或组织", en: "Individual Processor or Organization" },
  joint_controller: { zh: "共同控制者", en: "Joint Controller" },
  large_platform_operator: { zh: "大型平台运营者", en: "Large Platform Operator" },
  local_government_department: { zh: "地方政府部门", en: "Local Government Department" },
  member_state: { zh: "成员国", en: "Member State" },
  prc_competent_authority: { zh: "中国主管机关", en: "PRC Competent Authority" },
  processor: { zh: "处理者", en: "Processor" },
  public_affairs_organization: { zh: "公共事务管理组织", en: "Public Affairs Organization" },
  recipient: { zh: "接收方", en: "Recipient" },
  regulated_entity: { zh: "受监管实体", en: "Regulated Entity" },
  representative: { zh: "代表", en: "Representative" },
  service_provider: { zh: "服务提供者", en: "Service Provider" },
  state: { zh: "国家", en: "State" },
  state_council_department: { zh: "国务院有关部门", en: "State Council Department" },
  state_organ: { zh: "国家机关", en: "State Organ" },
  supervisory_authority: { zh: "监管机构", en: "Supervisory Authority" },
  third_party: { zh: "第三方", en: "Third Party" },
  trustee: { zh: "受托人", en: "Trustee" },
};

const GDPR_CATEGORY_BY_ARTICLE = {
  1: "general",
  2: "general",
  3: "general",
  4: "general",
  5: "general",
  6: "lawful_basis",
  7: "consent",
  8: "consent",
  9: "sensitive_data",
  10: "sensitive_data",
  11: "general",
  12: "transparency",
  13: "transparency",
  14: "transparency",
  15: "data_subject_rights",
  16: "data_subject_rights",
  17: "data_subject_rights",
  18: "data_subject_rights",
  19: "data_subject_rights",
  20: "data_subject_rights",
  21: "data_subject_rights",
  22: "data_subject_rights",
  23: "data_subject_rights",
  24: "accountability",
  25: "accountability",
  26: "accountability",
  27: "governance",
  28: "accountability",
  29: "accountability",
  30: "accountability",
  31: "governance",
  32: "security",
  33: "notification",
  34: "notification",
  35: "accountability",
  36: "governance",
  37: "governance",
  38: "governance",
  39: "accountability",
  40: "governance",
  41: "governance",
  42: "governance",
  43: "governance",
  44: "cross_border",
  45: "cross_border",
  46: "cross_border",
  47: "cross_border",
  48: "cross_border",
  49: "cross_border",
  50: "cross_border",
  51: "governance",
  52: "governance",
  53: "governance",
  54: "governance",
  55: "governance",
  56: "governance",
  57: "governance",
  58: "governance",
  59: "governance",
  60: "governance",
  61: "governance",
  62: "governance",
  63: "governance",
  64: "governance",
  65: "governance",
  66: "governance",
  67: "governance",
  68: "governance",
  69: "governance",
  70: "governance",
  71: "governance",
  72: "governance",
  73: "governance",
  74: "governance",
  75: "governance",
  76: "governance",
  77: "enforcement",
  78: "enforcement",
  79: "enforcement",
  80: "enforcement",
  81: "enforcement",
  82: "enforcement",
  83: "enforcement",
  84: "enforcement",
  85: "governance",
  86: "transparency",
  87: "sensitive_data",
  88: "governance",
  89: "governance",
  90: "governance",
  91: "governance",
  92: "governance",
  93: "governance",
  94: "general",
  95: "general",
  96: "general",
  97: "general",
  98: "general",
  99: "general",
};

const GDPR_IMPORTANCE_5 = new Set([
  3, 5, 6, 7, 9, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 24, 25, 28, 30, 32,
  33, 34, 35, 37, 44, 45, 46, 49, 51, 58, 77, 82, 83,
]);

const GDPR_IMPORTANCE_4 = new Set([
  8, 19, 23, 26, 27, 29, 31, 36, 38, 39, 40, 41, 42, 43, 47, 48, 52, 55, 56,
  57, 59, 66, 67, 68, 70, 71, 76, 84, 87, 89,
]);

const GDPR_KEY_ARTICLES = new Set([
  3, 5, 6, 7, 9, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 24, 25, 28, 30, 32,
  33, 34, 35, 37, 44, 45, 46, 49, 51, 58, 77, 82, 83,
]);

const CCPA_KEY_CLAUSE_REFS = new Set([
  "Section 1798.100",
  "Section 1798.105",
  "Section 1798.106",
  "Section 1798.110",
  "Section 1798.115",
  "Section 1798.120",
  "Section 1798.121",
  "Section 1798.125",
  "Section 1798.130",
  "Section 1798.135",
  "Section 1798.140",
  "Section 1798.145",
  "Section 1798.148",
  "Section 1798.150",
  "Section 1798.155",
  "Section 1798.185",
  "Section 1798.199.100",
]);

const CCPA_TITLE_BACKFILL = {
  "Section 1798.146": "Health, Medical, and Research Exemptions",
  "Section 1798.148": "Deidentified Information",
  "Section 1798.198": "Operative Provisions",
  "Section 1798.199.10": "Agency Structure",
  "Section 1798.199.45": "Agency Complaints",
  "Section 1798.199.55": "Agency Orders and Administrative Fines",
  "Section 1798.199.75": "Agency Civil Actions",
  "Section 1798.199.80": "Judgment Enforcement",
  "Section 1798.199.90": "Attorney General Enforcement",
  "Section 1798.199.95": "Agency Funding and Threshold Adjustments",
};

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function titleize(token) {
  return token
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function firstNonEmpty(...values) {
  for (const value of values) {
    if (value == null) {
      continue;
    }
    if (typeof value === "string" && value.trim() === "") {
      continue;
    }
    return value;
  }
  return null;
}

function extractArticleNumber(articleReference) {
  const match = String(articleReference || "").match(/(\d+)/);
  return match ? Number(match[1]) : null;
}

function normalizeArticleReference(lawId, articleReference) {
  if (!articleReference) {
    return articleReference;
  }
  if (lawId === "US_CA_CCPA_CPRA_2018") {
    return String(articleReference)
      .replace(/^[§\s]+/, "")
      .replace(/^1798\./, "1798.")
      .replace(/^Section\s+/i, "")
      .trim()
      .replace(/^/, "Section ");
  }
  return articleReference;
}

function incrementCounter(map, key) {
  if (!key) {
    return;
  }
  map[key] = (map[key] || 0) + 1;
}

function buildClauseLookup(dataSets) {
  const byLawAndArticle = new Map();
  const byLawAndLocalArticle = new Map();
  const byLawAndClauseId = new Map();

  for (const data of dataSets) {
    const lawId = data.law.law_id;
    for (const clause of data.clauses) {
      byLawAndClauseId.set(`${lawId}::${clause.clause_id}`, clause);
      if (clause.article_reference) {
        byLawAndArticle.set(
          `${lawId}::${normalizeArticleReference(lawId, clause.article_reference)}`,
          clause,
        );
      }
      if (clause.article_reference_local) {
        byLawAndLocalArticle.set(
          `${lawId}::${clause.article_reference_local}`,
          clause,
        );
      }
    }
  }

  return { byLawAndArticle, byLawAndLocalArticle, byLawAndClauseId };
}

function countPendingTranslations(dataSets) {
  let pendingClauseText = 0;
  let pendingObligationStatement = 0;
  let nullTitleEn = 0;
  let nullTextEn = 0;
  let nullStatementEn = 0;

  for (const data of dataSets) {
    for (const clause of data.clauses) {
      if (
        !clause.title ||
        clause.title.en == null ||
        String(clause.title.en).trim() === ""
      ) {
        nullTitleEn += 1;
      }
      if (clause.text_en == null) {
        nullTextEn += 1;
      }
      if (clause.text_en_source === "pending") {
        pendingClauseText += 1;
      }
    }
    for (const obligation of data.obligations) {
      if (obligation.statement_en == null) {
        nullStatementEn += 1;
      }
      if (obligation.statement_en_source === "pending") {
        pendingObligationStatement += 1;
      }
    }
  }

  return {
    pendingClauseText,
    pendingObligationStatement,
    nullTitleEn,
    nullTextEn,
    nullStatementEn,
  };
}

function optimizePipl(pipl) {
  const report = {
    chapterTitleEnBackfilled: 0,
    sectionTitleEnBackfilled: 0,
    summaryKeyClausesEnriched: 0,
  };

  for (const clause of pipl.clauses) {
    if (clause.chapter_title && !clause.chapter_title.en) {
      const translated = PIPL_CHAPTER_TITLE_EN[clause.chapter_title.zh];
      if (translated) {
        clause.chapter_title.en = translated;
        report.chapterTitleEnBackfilled += 1;
      }
    }
    if (clause.section_title && !clause.section_title.en) {
      const translated = PIPL_SECTION_TITLE_EN[clause.section_title.zh];
      if (translated) {
        clause.section_title.en = translated;
        report.sectionTitleEnBackfilled += 1;
      }
    }
  }

  report.summaryKeyClausesEnriched = enrichSummaryKeyClauses(pipl);
  recalculateSummary(pipl);
  return report;
}

function deriveGdprImportance(articleNumber) {
  if (GDPR_IMPORTANCE_5.has(articleNumber)) {
    return 5;
  }
  if (GDPR_IMPORTANCE_4.has(articleNumber)) {
    return 4;
  }
  if (articleNumber >= 92) {
    return 2;
  }
  return 3;
}

function optimizeGdpr(gdpr) {
  const report = {
    clauseCategoriesBackfilled: 0,
    obligationCategoriesBackfilled: 0,
    importanceBackfilled: 0,
    keyClauseFlagsBackfilled: 0,
    summaryKeyClausesGenerated: 0,
  };

  const clauseById = new Map();

  for (const clause of gdpr.clauses) {
    const articleNumber = extractArticleNumber(clause.article_reference);
    const category = GDPR_CATEGORY_BY_ARTICLE[articleNumber] || "general";
    if (clause.category !== category) {
      clause.category = category;
      report.clauseCategoriesBackfilled += 1;
    }

    const importance = deriveGdprImportance(articleNumber);
    if (clause.importance !== importance) {
      clause.importance = importance;
      report.importanceBackfilled += 1;
    }

    const isKeyClause = GDPR_KEY_ARTICLES.has(articleNumber);
    if (clause.is_key_clause !== isKeyClause) {
      clause.is_key_clause = isKeyClause;
      report.keyClauseFlagsBackfilled += 1;
    }

    clauseById.set(clause.clause_id, clause);
  }

  for (const obligation of gdpr.obligations) {
    const clause = clauseById.get(obligation.clause_id);
    const category = clause ? clause.category : "general";
    if (obligation.category !== category) {
      obligation.category = category;
      report.obligationCategoriesBackfilled += 1;
    }
  }

  gdpr.summary.key_clauses = gdpr.clauses
    .filter((clause) => clause.is_key_clause)
    .sort((left, right) => {
      return (
        extractArticleNumber(left.article_reference) -
        extractArticleNumber(right.article_reference)
      );
    })
    .map((clause) => makeSummaryKeyClause(clause));
  report.summaryKeyClausesGenerated = gdpr.summary.key_clauses.length;

  recalculateSummary(gdpr);
  return report;
}

function optimizeCcpa(ccpa) {
  const report = {
    titleEnBackfilled: 0,
    keyClauseFlagsBackfilled: 0,
    summaryKeyClausesEnriched: 0,
  };

  for (const clause of ccpa.clauses) {
    if (clause.title && String(clause.title.en || "").trim() === "") {
      clause.title.en =
        CCPA_TITLE_BACKFILL[clause.article_reference] || titleize(clause.category || "");
      report.titleEnBackfilled += 1;
    }

    const isKeyClause = CCPA_KEY_CLAUSE_REFS.has(clause.article_reference);
    if (clause.is_key_clause !== isKeyClause) {
      clause.is_key_clause = isKeyClause;
      report.keyClauseFlagsBackfilled += 1;
    }
  }

  report.summaryKeyClausesEnriched = enrichSummaryKeyClauses(ccpa);
  recalculateSummary(ccpa);
  return report;
}

function makeSummaryKeyClause(clause) {
  return {
    article_reference: clause.article_reference || null,
    article_reference_local: clause.article_reference_local || null,
    title: {
      zh: clause.title?.zh ?? null,
      en: clause.title?.en ?? null,
    },
    category: clause.category || null,
  };
}

function enrichSummaryKeyClauses(data) {
  if (!data.summary || !Array.isArray(data.summary.key_clauses)) {
    return 0;
  }

  const byClauseId = new Map();
  const byArticleReference = new Map();
  const byLocalArticleReference = new Map();

  for (const clause of data.clauses) {
    byClauseId.set(clause.clause_id, clause);
    if (clause.article_reference) {
      byArticleReference.set(clause.article_reference, clause);
    }
    if (clause.article_reference_local) {
      byLocalArticleReference.set(clause.article_reference_local, clause);
    }
  }

  let enriched = 0;
  const normalized = [];
  const seen = new Set();

  for (const keyClauseEntry of data.summary.key_clauses) {
    let clause = null;
    let draft =
      typeof keyClauseEntry === "string"
        ? { article_reference: keyClauseEntry }
        : { ...keyClauseEntry };

    if (draft.clause_id) {
      clause = byClauseId.get(draft.clause_id) || null;
    }
    if (!clause && draft.article_reference) {
      clause = byArticleReference.get(draft.article_reference) || null;
    }
    if (!clause && draft.article_reference_local) {
      clause = byLocalArticleReference.get(draft.article_reference_local) || null;
    }

    if (clause) {
      draft = {
        article_reference: firstNonEmpty(
          draft.article_reference,
          clause.article_reference,
        ),
        article_reference_local: firstNonEmpty(
          draft.article_reference_local,
          clause.article_reference_local,
        ),
        title: {
          zh: firstNonEmpty(draft.title?.zh, clause.title?.zh),
          en: firstNonEmpty(draft.title?.en, clause.title?.en),
        },
        category: firstNonEmpty(draft.category, clause.category),
      };
      enriched += 1;
    } else {
      draft = {
        article_reference: firstNonEmpty(draft.article_reference),
        article_reference_local: firstNonEmpty(draft.article_reference_local),
        title: {
          zh: firstNonEmpty(draft.title?.zh),
          en: firstNonEmpty(draft.title?.en),
        },
        category: firstNonEmpty(draft.category),
      };
    }

    const dedupeKey =
      draft.article_reference ||
      draft.article_reference_local ||
      JSON.stringify(draft.title);
    if (seen.has(dedupeKey)) {
      continue;
    }
    seen.add(dedupeKey);
    normalized.push(draft);
  }

  data.summary.key_clauses = normalized;
  return enriched;
}

function recalculateSummary(data) {
  const summary = data.summary || {};
  data.summary = summary;

  const clausesByCategory = {};
  const obligationsByType = {};
  const obligationsByActor = {};

  for (const clause of data.clauses) {
    incrementCounter(clausesByCategory, clause.category);
  }
  for (const obligation of data.obligations) {
    incrementCounter(obligationsByType, obligation.type);
    incrementCounter(obligationsByActor, obligation.actor);
  }

  summary.law_id = data.law.law_id;
  summary.clauses_by_category = sortRecord(clausesByCategory);
  summary.obligations_by_type = sortRecord(obligationsByType);
  summary.obligations_by_actor = sortRecord(obligationsByActor);

  data.law.clause_count = data.clauses.length;
  data.law.obligation_count = data.obligations.length;
}

function sortRecord(record) {
  return Object.fromEntries(
    Object.entries(record).sort((left, right) => left[0].localeCompare(right[0])),
  );
}

function ensureVocabularyCoverage(baseVocabulary, dataSets) {
  const vocabulary = deepClone(baseVocabulary || DEFAULT_VOCABULARY);
  vocabulary.obligation_types = vocabulary.obligation_types || {};
  vocabulary.actors = vocabulary.actors || {};
  vocabulary.categories = vocabulary.categories || {};
  vocabulary.jurisdictions = vocabulary.jurisdictions || DEFAULT_VOCABULARY.jurisdictions;

  const obligationTypes = new Set();
  const actors = new Set();
  const categories = new Set();

  for (const data of dataSets) {
    for (const clause of data.clauses) {
      if (clause.category) {
        categories.add(clause.category);
      }
    }
    for (const obligation of data.obligations) {
      if (obligation.type) {
        obligationTypes.add(obligation.type);
      }
      if (obligation.actor) {
        actors.add(obligation.actor);
      }
      if (obligation.category) {
        categories.add(obligation.category);
      }
    }
  }

  for (const obligationType of obligationTypes) {
    if (!vocabulary.obligation_types[obligationType]) {
      vocabulary.obligation_types[obligationType] =
        OBLIGATION_TYPE_LABELS[obligationType] || {
          zh: null,
          en: titleize(obligationType),
        };
    }
  }

  for (const actor of actors) {
    if (!vocabulary.actors[actor]) {
      vocabulary.actors[actor] = ACTOR_LABELS[actor] || {
        zh: null,
        en: titleize(actor),
      };
    }
  }

  for (const category of categories) {
    if (!vocabulary.categories[category]) {
      vocabulary.categories[category] = {
        zh: null,
        en: titleize(category),
      };
    }
  }

  vocabulary.obligation_types = sortNestedLabels(vocabulary.obligation_types);
  vocabulary.actors = sortNestedLabels(vocabulary.actors);
  vocabulary.categories = sortNestedLabels(vocabulary.categories);
  vocabulary.jurisdictions = sortNestedLabels(vocabulary.jurisdictions);
  return vocabulary;
}

function sortNestedLabels(record) {
  return Object.fromEntries(
    Object.entries(record)
      .sort((left, right) => left[0].localeCompare(right[0]))
      .map(([key, value]) => [
        key,
        {
          zh: value?.zh ?? null,
          en: value?.en ?? titleize(key),
        },
      ]),
  );
}

function buildUnifiedGraph(dataSets, currentUnified) {
  const vocabulary = ensureVocabularyCoverage(
    currentUnified?.vocabulary || DEFAULT_VOCABULARY,
    dataSets,
  );

  const links = fixCrossJurisdictionLinks(
    currentUnified?.cross_jurisdiction_links || [],
    dataSets,
  );

  const translationStatus = countPendingTranslations(dataSets);
  const pendingTranslations =
    translationStatus.pendingClauseText === 0 &&
    translationStatus.pendingObligationStatement === 0
      ? "none"
      : `pending clause text translations: ${translationStatus.pendingClauseText}; pending obligation statement translations: ${translationStatus.pendingObligationStatement}`;

  const laws = dataSets.map((data) => data.law);
  const clauses = dataSets.flatMap((data) => data.clauses);
  const obligations = dataSets.flatMap((data) => data.obligations);
  const relations = dataSets.flatMap((data) => data.relations);
  const summaries = dataSets.map((data) => data.summary);

  return {
    meta: {
      schema_version: currentUnified?.meta?.schema_version || "1.0.0",
      jurisdictions: ["CN", "EU", "US"],
      laws: laws.map((law) => law.law_id),
      total_clauses: clauses.length,
      total_obligations: obligations.length,
      total_relations: relations.length,
      bilingual_fields: [
        "title",
        "chapter_title",
        "section_title",
        "text_en",
        "statement_en",
      ],
      pending_translations: pendingTranslations,
    },
    vocabulary,
    laws,
    clauses,
    obligations,
    relations,
    cross_jurisdiction_links: links,
    summaries,
  };
}

function fixCrossJurisdictionLinks(crossJurisdictionLinks, dataSets) {
  const clauseLookup = buildClauseLookup(dataSets);
  const lawIdMap = {
    PIPL: "CN_PIPL_2021",
    GDPR: "EU_GDPR_2016_679",
    CCPA: "US_CA_CCPA_CPRA_2018",
  };

  return crossJurisdictionLinks.map((link) => {
    const nodes = (link.nodes || []).map((node) => {
      const lawId = lawIdMap[node.law_id] || node.law_id;
      const articleReference = normalizeArticleReference(
        lawId,
        node.article_reference || null,
      );
      const localArticleReference = node.article_reference_local || null;

      let clause = null;
      if (node.clause_id) {
        clause =
          clauseLookup.byLawAndClauseId.get(`${lawId}::${node.clause_id}`) || null;
      }
      if (!clause && articleReference) {
        clause =
          clauseLookup.byLawAndArticle.get(`${lawId}::${articleReference}`) || null;
      }
      if (!clause && localArticleReference) {
        clause =
          clauseLookup.byLawAndLocalArticle.get(
            `${lawId}::${localArticleReference}`,
          ) || null;
      }

      return {
        law_id: lawId,
        clause_id: clause ? clause.clause_id : node.clause_id || null,
        article_reference: articleReference,
        article_reference_local:
          localArticleReference || clause?.article_reference_local || null,
      };
    });

    return {
      ...link,
      nodes,
    };
  });
}

function validateDataSets(dataSets, unified) {
  const clauseIds = new Set();
  const obligationIds = new Set();
  const relationIssues = [];
  let duplicateClauseIds = 0;
  let duplicateObligationIds = 0;

  for (const clause of unified.clauses) {
    if (clauseIds.has(clause.clause_id)) {
      duplicateClauseIds += 1;
    }
    clauseIds.add(clause.clause_id);
  }

  for (const obligation of unified.obligations) {
    if (obligationIds.has(obligation.obligation_id)) {
      duplicateObligationIds += 1;
    }
    obligationIds.add(obligation.obligation_id);
  }

  const obligationIdSet = new Set(unified.obligations.map((item) => item.obligation_id));

  for (const relation of unified.relations) {
    if (
      relation.source_type === "law" &&
      !unified.laws.some((law) => law.law_id === relation.source_id)
    ) {
      relationIssues.push(relation.relation_id);
    }
    if (
      relation.target_type === "clause" &&
      !clauseIds.has(relation.target_id)
    ) {
      relationIssues.push(relation.relation_id);
    }
    if (
      relation.source_type === "clause" &&
      !clauseIds.has(relation.source_id)
    ) {
      relationIssues.push(relation.relation_id);
    }
    if (
      relation.target_type === "obligation" &&
      !obligationIdSet.has(relation.target_id)
    ) {
      relationIssues.push(relation.relation_id);
    }
  }

  let invalidCrossLinkNodes = 0;
  for (const link of unified.cross_jurisdiction_links) {
    for (const node of link.nodes || []) {
      if (!unified.laws.some((law) => law.law_id === node.law_id)) {
        invalidCrossLinkNodes += 1;
        continue;
      }
      if (node.clause_id && !clauseIds.has(node.clause_id)) {
        invalidCrossLinkNodes += 1;
      }
    }
  }

  const translationStatus = countPendingTranslations(dataSets);
  const summaryKeyClauseIssues = {};

  for (const data of dataSets) {
    const unresolved = (data.summary?.key_clauses || []).filter((entry) => {
      return (
        !entry.title ||
        (!String(entry.title.en || "").trim() && !String(entry.title.zh || "").trim())
      );
    }).length;
    summaryKeyClauseIssues[data.law.law_id] = unresolved;
  }

  return {
    duplicateClauseIds,
    duplicateObligationIds,
    danglingRelations: relationIssues.length,
    invalidCrossLinkNodes,
    ...translationStatus,
    summaryKeyClauseIssues,
  };
}

function main() {
  const pipl = readJson(FILES.pipl);
  const gdpr = readJson(FILES.gdpr);
  const ccpa = readJson(FILES.ccpa);
  const currentUnified = readJson(FILES.unified);

  const report = {
    generated_at: new Date().toISOString(),
    files: {
      PIPL_normalized_json: optimizePipl(pipl),
      GDPR_normalized_json: optimizeGdpr(gdpr),
      CCPA_normalized_json: optimizeCcpa(ccpa),
    },
  };

  const dataSets = [pipl, gdpr, ccpa];
  const unified = buildUnifiedGraph(dataSets, currentUnified);
  const validation = validateDataSets(dataSets, unified);

  report.unified = {
    law_count: unified.laws.length,
    clause_count: unified.clauses.length,
    obligation_count: unified.obligations.length,
    relation_count: unified.relations.length,
    cross_jurisdiction_link_count: unified.cross_jurisdiction_links.length,
    vocabulary: {
      obligation_types: Object.keys(unified.vocabulary.obligation_types).length,
      actors: Object.keys(unified.vocabulary.actors).length,
      categories: Object.keys(unified.vocabulary.categories).length,
    },
  };
  report.validation = validation;

  writeJson(FILES.pipl, pipl);
  writeJson(FILES.gdpr, gdpr);
  writeJson(FILES.ccpa, ccpa);
  writeJson(FILES.unified, unified);
  writeJson(FILES.report, report);

  console.log(JSON.stringify(report, null, 2));
}

main();
