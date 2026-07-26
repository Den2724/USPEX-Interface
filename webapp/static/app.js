let logVersion = 0;
let appState = null;
const openPreviewByN = {};
let browserState = { root: "", current: "" };
let browserListingData = { dirs: [], files: [] };
let formHydrated = false;
let expectedPreviewText = "";
let previewSyncTimer = null;
let pathSaveTimer = null;
let mpSaveTimer = null;
const seedTextOpenByKey = {};
const seedGroupOpenById = {};
const antiSeedTextOpenByKey = {};
const antiSeedGroupOpenById = {};
let seedGenerationEditing = false;
let antiSeedGenerationEditing = false;
const browserFileOpenByPath = {};
const browserFileContentByPath = {};
let topToastTimer = null;
const copyHintTimers = new WeakMap();
let lastPreviewStructuresSignature = "";
let boomLaunched = false;
let boomFinishTimer = null;
let boomClearTimer = null;
let sunsetLaunched = false;
let sunsetFinishTimer = null;
let sunsetClearTimer = null;
let waveLaunched = false;
let waveFinishTimer = null;
let waveClearTimer = null;
let waveSpawnerTimer = null;
let waveDripTimer = null;
let currentThemePalette = {
  primary: "#2E86AB",
  bg: "#F1F7FB",
  text: "#0B1F2A",
};
let lastUserScrollAt = 0;
let refreshInFlight = false;
let pollLogInFlight = false;
let lastSeedGroupsSignature = "";
let lastAntiSeedGroupsSignature = "";
let specificEnabled = false;
let specificFiles = [];
let specificEditorIndex = -1;
let specificNameEditingIndex = -1;
let specificSaveTimer = null;
const mpStatusTimers = {};
const UI_THEME_STORAGE_KEY = "uspex_ui_theme";
const UI_LANG_STORAGE_KEY = "uspex_ui_lang";
const ADV_GROUP_OPEN_STORAGE_KEY = "uspex_adv_group_open_by_index";
const SEED_GROUP_OPEN_STORAGE_KEY = "uspex_seed_group_open_by_id";
const SEED_TEXT_OPEN_STORAGE_KEY = "uspex_seed_text_open_by_key";
const ANTI_SEED_GROUP_OPEN_STORAGE_KEY = "uspex_anti_seed_group_open_by_id";
const ANTI_SEED_TEXT_OPEN_STORAGE_KEY = "uspex_anti_seed_text_open_by_key";
const UI_THEMES = [
  { name: "Ocean", icon: "🟦", primary: "#2E86AB", bg: "#F1F7FB", text: "#0B1F2A" },
  { name: "Forest", icon: "🟩", primary: "#2D6A4F", bg: "#F4FBF7", text: "#0E241B" },
  { name: "Sunset", icon: "🟧", primary: "#E76F51", bg: "#FFF3EC", text: "#3A1E16" },
  { name: "Violet Pulse", icon: "🟪", primary: "#7B2CBF", bg: "#F7F0FF", text: "#2B103B" },
  { name: "Deep Blue", icon: "🟦", primary: "#1D4ED8", bg: "#EFF6FF", text: "#0B1A4A" },
  { name: "Noir", icon: "⬛", primary: "#111827", bg: "#F2F2F2", text: "#0F0F0F" },
  { name: "White Linen", icon: "⬜", primary: "#E5E7EB", bg: "#FFFFFF", text: "#111827" },
  { name: "Pink Bloom", icon: "🩷", primary: "#EC4899", bg: "#FFF1F8", text: "#4A0C2C" },
];
const browserPanelSizeSnapshot = {
  active: false,
  width: "",
  maxWidth: "",
  minHeight: "",
  pxWidth: 0,
};
const advGroupOpenByIndex = {};

function loadAdvGroupOpenState() {
  try {
    const raw = localStorage.getItem(ADV_GROUP_OPEN_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return;
    for (const [k, v] of Object.entries(parsed)) {
      const idx = Number(k);
      if (!Number.isFinite(idx)) continue;
      advGroupOpenByIndex[idx] = v !== false;
    }
  } catch (_e) {}
}

function saveAdvGroupOpenState() {
  try {
    localStorage.setItem(ADV_GROUP_OPEN_STORAGE_KEY, JSON.stringify(advGroupOpenByIndex));
  } catch (_e) {}
}

function loadObjectMapFromStorage(key, target) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return;
    for (const [k, v] of Object.entries(parsed)) {
      target[k] = !!v;
    }
  } catch (_e) {}
}

function saveObjectMapToStorage(key, source) {
  try {
    localStorage.setItem(key, JSON.stringify(source));
  } catch (_e) {}
}

const MODES = ["fixed", "single", "variable"];
const ADV_GROUPS = [
  {
    title: "System Type and Core Parameters",
    fields: [
      { key: "calculationMethod", tip: "Sets the calculation method (USPEX by default, evolutionary prediction)." },
      { key: "calculationType", tip: "Defines the task type via dimensionality, molecular mode, and composition variability." },
      { key: "optType", tip: "Chooses optimization target(s), e.g., enthalpy, volume, density, or band gap." },
      { key: "atomType", tip: "Atom-type identifiers: element symbols, names, or periodic table numbers." },
      { key: "numSpecies", tip: "Number of atoms, molecules, or compositional blocks per type in the cell." },
      { key: "ExternalPressure", tip: "External pressure in GPa for structure stability search." },
      { key: "valences", tip: "Valences per atom type, mainly used for bond hardness and phonon-related logic." },
      { key: "goodBonds", tip: "Square matrix of minimal valence contacts treated as significant bonds." },
      { key: "checkConnectivity", tip: "1/0 switch for connectivity and bond-hardness checks." },
      { key: "fitLimit", tip: "Threshold of target fitness/property for successful early stop." },
    ],
  },
  {
    title: "Population and Selection",
    fields: [
      { key: "populationSize", tip: "Number of structures in each generation." },
      { key: "initialPopSize", tip: "Size of initial generation; often larger than populationSize." },
      { key: "numGenerations", tip: "Maximum allowed number of generations." },
      { key: "stopCrit", tip: "Early-stop criterion, e.g., unchanged best structure over N generations." },
      { key: "bestFrac", tip: "Fraction of best structures selected as parents." },
      { key: "keepBestHM", tip: "Number of top structures guaranteed to survive to next generation." },
      { key: "reoptOld", tip: "Whether survivors are re-relaxed (0 no, 1 yes)." },
    ],
  },
  {
    title: "Structure Generation and Variation Operators",
    fields: [
      { key: "symmetries", tip: "Allowed space-group numbers for random symmetric generation." },
      { key: "splitInto", tip: "Number of identical subcells/pseudosubcells for large systems." },
      { key: "fracGene", tip: "Fraction created by heredity/crossover operators." },
      { key: "fracRand", tip: "Fraction created by random symmetric generation." },
      { key: "fracTopRand", tip: "Fraction created by topological random generator." },
      { key: "fracPerm", tip: "Fraction created by permutation of atom types." },
      { key: "fracAtomsMut", tip: "Fraction created by soft/coordinate mutation." },
      { key: "fracPyXTal", tip: "Fraction created via PyXtal generator." },
      { key: "howManySwaps", tip: "Maximum number of pair swaps for permutation operator." },
      { key: "specificSwaps", tip: "Restricts swaps to selected element pairs only." },
      { key: "AutoFrac", tip: "1/0 smart auto-tuning of variation-operator fractions during run." },
    ],
  },
  {
    title: "Constraints and Cell Setup",
    fields: [
      { key: "minVectorLength", tip: "Minimum allowed lattice-vector length for generated structures." },
      { key: "IonDistances", tip: "Pairwise minimum interatomic distance matrix; structures below are rejected." },
      { key: "constraintEnhancement", tip: "Temporarily tightens IonDistances for symmetric random structures." },
      { key: "Latticevalues", tip: "Initial cell volume/lattice parameters (3x3 matrix or a,b,c with angles)." },
    ],
  },
  {
    title: "Ab Initio and Job Execution",
    fields: [
      { key: "abinitioCode", tip: "External code per relaxation step (e.g., 1 VASP, 3 GULP, 5 ORCA)." },
      { key: "KresolStart", tip: "Initial k-point resolution for staged relaxation." },
      { key: "vacuumSize", tip: "Vacuum thickness (A) for surfaces, clusters, or 2D systems." },
      { key: "numParallelCalcs", tip: "Number of structure relaxations executed in parallel." },
      { key: "commandExecutable", tip: "Launch commands/scripts for external code at each relaxation step." },
      { key: "whichCluster", tip: "Job mode: 0 no scripts, 1 local workstation, 2 remote cluster." },
      { key: "remoteFolder", tip: "Remote cluster directory path (used when whichCluster=2)." },
      { key: "PhaseDiagram", tip: "Enables preliminary phase-stability scan over pressures." },
      { key: "coresPerJob", tip: "CPU cores allocated per local relaxation job." },
      { key: "sleepSeconds", tip: "Delay in seconds before starting next sequential relaxations." },
    ],
  },
  {
    title: "Restart and Postprocessing",
    fields: [
      { key: "pickUpGen", tip: "Generation number to continue interrupted run from." },
      { key: "pickUpFolder", tip: "Results folder index (resultsX) to resume from." },
      { key: "RmaxFing", tip: "Cutoff radius (A) for fingerprint calculation." },
      { key: "deltaFing", tip: "Discretization step for fingerprint function." },
      { key: "sigmaFing", tip: "Gaussian broadening for fingerprint interatomic distances." },
      { key: "doSpaceGroup", tip: "Enables symmetry detection (spglib) and CIF export." },
      { key: "SymTolerance", tip: "Tolerance used for symmetry search." },
    ],
  },
  {
    title: "Variable Composition Parameters",
    fields: [
      { key: "firstGeneMax", tip: "Number of random compositions in the initial generation." },
      { key: "fracTrans", tip: "Fraction created by transmutation operator." },
      { key: "howManyTrans", tip: "Maximum percent of atoms transmuted in a structure." },
    ],
  },
  {
    title: "Rare / Developer Parameters",
    fields: [
      { key: "mutationRate", tip: "Std. deviation of deformation-matrix components for lattice mutation." },
      { key: "mutationDegree", tip: "Maximum atomic displacement (A) in soft mutation." },
      { key: "orderingActive", tip: "Enables local-order parameters in variation-operator behavior." },
      { key: "symmetrize", tip: "Transforms outgoing structures to standard crystallographic settings." },
      { key: "valenceElectr", tip: "Valence electrons per atom type (usually built in)." },
      { key: "percSliceShift", tip: "Probability of additional layer shift in heredity operator." },
      { key: "maxDistHeredity", tip: "Maximum fingerprint cosine distance allowed for crossover parents." },
      { key: "manyParents", tip: "Allows >2 parent structures/layers in crossover." },
      { key: "minSlice", tip: "Minimum layer thickness (A) cut from parents for offspring." },
      { key: "maxSlice", tip: "Maximum layer thickness (A) cut from parents for offspring." },
      { key: "repeatForStatistics", tip: "Repeats runs automatically for algorithmic statistics collection." },
      { key: "stopFitness", tip: "Target fitness threshold for repeat-run stopping." },
      { key: "fixRndSeed", tip: "Fixes random seed for fully reproducible runs." },
      { key: "collectForces", tip: "Collects forces/positions/stress from VASP into FORCE.mat for ML." },
    ],
  },
];
const ADV_KEYS = ADV_GROUPS.flatMap((group) => group.fields.map((field) => field.key));
const ADV_MULTILINE_KEYS = new Set(["goodBonds", "IonDistances", "commandExecutable"]);
const ADV_FIELD_BY_KEY = Object.fromEntries(
  ADV_GROUPS.flatMap((group) => group.fields.map((field) => [field.key, field]))
);
const ADV_GROUP_TITLES = {
  en: [
    "System Type and Core Parameters",
    "Population and Selection",
    "Structure Generation and Variation Operators",
    "Constraints and Cell Setup",
    "Ab Initio and Job Execution",
    "Restart and Postprocessing",
    "Variable Composition Parameters",
    "Rare / Developer Parameters",
  ],
  ru: [
    "Тип системы и основные параметры",
    "Популяция и отбор",
    "Генерация структур и операторы вариации",
    "Ограничения и параметры ячейки",
    "Ab Initio и выполнение задач",
    "Перезапуск и постобработка",
    "Параметры переменного состава",
    "Редкие / разработческие параметры",
  ],
  zh: [
    "体系类型与核心参数",
    "种群与选择",
    "结构生成与变异算子",
    "约束与晶胞设置",
    "Ab Initio 与任务执行",
    "重启与后处理",
    "可变组分参数",
    "稀有 / 开发者参数",
  ],
  fa: [
    "نوع سیستم و پارامترهای اصلی",
    "جمعیت و انتخاب",
    "تولید ساختار و عملگرهای تغییر",
    "قیود و تنظیمات سلول",
    "Ab Initio و اجرای کار",
    "ادامه اجرا و پس‌پردازش",
    "پارامترهای ترکیب متغیر",
    "پارامترهای نادر / توسعه‌دهنده",
  ],
  hi: [
    "सिस्टम प्रकार और मुख्य पैरामीटर",
    "जनसंख्या और चयन",
    "संरचना निर्माण और परिवर्तन ऑपरेटर",
    "बंधन और सेल सेटअप",
    "Ab Initio और जॉब निष्पादन",
    "रीस्टार्ट और पोस्टप्रोसेसिंग",
    "वैरिएबल कंपोज़िशन पैरामीटर",
    "दुर्लभ / डेवलपर पैरामीटर",
  ],
};
const ADV_TIP_RULES = {
  ru: [
    ["Sets the calculation method", "Задаёт метод расчёта"],
    ["Defines the task type", "Определяет тип задачи"],
    ["Chooses optimization target(s)", "Выбирает целевые параметры оптимизации"],
    ["Atom-type identifiers", "Идентификаторы типов атомов"],
    ["Number of atoms, molecules, or compositional blocks per type in the cell.", "Количество атомов, молекул или композиционных блоков каждого типа в ячейке."],
    ["External pressure in GPa for structure stability search.", "Внешнее давление в ГПа для поиска стабильных структур."],
    ["Valences per atom type", "Валентности для каждого типа атомов"],
    ["Square matrix of minimal valence contacts treated as significant bonds.", "Квадратная матрица минимальных валентных контактов, считающихся значимыми связями."],
    ["1/0 switch for connectivity and bond-hardness checks.", "Переключатель 1/0 для проверки связности и жёсткости связей."],
    ["Threshold of target fitness/property for successful early stop.", "Порог целевой функции/свойства для досрочной остановки."],
    ["Number of structures in each generation.", "Количество структур в каждом поколении."],
    ["Size of initial generation; often larger than populationSize.", "Размер начального поколения; обычно больше populationSize."],
    ["Maximum allowed number of generations.", "Максимально допустимое число поколений."],
    ["Early-stop criterion", "Критерий ранней остановки"],
    ["Fraction of best structures selected as parents.", "Доля лучших структур, выбираемых как родители."],
    ["Number of top structures guaranteed to survive to next generation.", "Количество лучших структур, гарантированно переходящих в следующее поколение."],
    ["Whether survivors are re-relaxed (0 no, 1 yes).", "Нужно ли заново релаксировать выжившие структуры (0 — нет, 1 — да)."],
    ["Allowed space-group numbers for random symmetric generation.", "Разрешённые номера пространственных групп для случайной симметричной генерации."],
    ["Fraction created by", "Доля, создаваемая оператором"],
    ["Maximum number of pair swaps for permutation operator.", "Максимальное число парных перестановок для оператора перестановки."],
    ["Restricts swaps to selected element pairs only.", "Ограничивает перестановки только выбранными парами элементов."],
    ["smart auto-tuning of variation-operator fractions during run.", "интеллектуальная автоподстройка долей операторов вариации во время расчёта."],
    ["Minimum allowed lattice-vector length for generated structures.", "Минимально допустимая длина вектора решётки для генерируемых структур."],
    ["Pairwise minimum interatomic distance matrix; structures below are rejected.", "Матрица минимальных попарных межатомных расстояний; структуры ниже порога отклоняются."],
    ["Temporarily tightens IonDistances for symmetric random structures.", "Временно ужесточает IonDistances для симметричных случайных структур."],
    ["Initial cell volume/lattice parameters", "Начальный объём ячейки/параметры решётки"],
    ["External code per relaxation step", "Внешний код для каждого шага релаксации"],
    ["Initial k-point resolution for staged relaxation.", "Начальное разрешение k-точек для поэтапной релаксации."],
    ["Final k-point resolution for staged relaxation.", "Финальное разрешение k-точек для поэтапной релаксации."],
    ["Vacuum thickness (A) for surfaces, clusters, or 2D systems.", "Толщина вакуума (A) для поверхностей, кластеров или 2D-систем."],
    ["Number of structure relaxations executed in parallel.", "Количество релаксаций структур, выполняемых параллельно."],
    ["Launch commands/scripts for external code at each relaxation step.", "Команды/скрипты запуска внешнего кода на каждом шаге релаксации."],
    ["Job mode", "Режим выполнения задач"],
    ["Remote cluster directory path", "Путь к директории удалённого кластера"],
    ["Enables preliminary phase-stability scan over pressures.", "Включает предварительное сканирование стабильности фаз по давлению."],
    ["CPU cores allocated per local relaxation job.", "Количество CPU-ядер на одну локальную релаксацию."],
    ["Delay in seconds before starting next sequential relaxations.", "Задержка в секундах перед запуском следующих последовательных релаксаций."],
    ["Generation number to continue interrupted run from.", "Номер поколения, с которого продолжать прерванный расчёт."],
    ["Results folder index", "Индекс папки результатов"],
    ["Cutoff radius (A) for fingerprint calculation.", "Радиус отсечения (A) для расчёта fingerprint."],
    ["Discretization step for fingerprint function.", "Шаг дискретизации функции fingerprint."],
    ["Gaussian broadening for fingerprint interatomic distances.", "Гауссово уширение межатомных расстояний в fingerprint."],
    ["Enables symmetry detection", "Включает определение симметрии"],
    ["Tolerance used for symmetry search.", "Допуск, используемый при поиске симметрии."],
    ["Number of random compositions in the initial generation.", "Количество случайных составов в начальном поколении."],
    ["Maximum percent of atoms transmuted in a structure.", "Максимальный процент атомов, подвергаемых трансмутации в структуре."],
    ["Fixes random seed for fully reproducible runs.", "Фиксирует зерно случайности для полностью воспроизводимых запусков."],
  ],
  zh: [
    ["Sets the", "设置"], ["Defines the", "定义"], ["Chooses", "选择"], ["Number of", "数量"],
    ["Maximum", "最大"], ["Minimum", "最小"], ["Fraction", "比例"], ["Enables", "启用"],
    ["Initial", "初始"], ["Final", "最终"], ["External", "外部"], ["Generation", "代"],
    ["structure", "结构"], ["structures", "结构"], ["relaxation", "弛豫"], ["symmetry", "对称性"],
  ],
  fa: [
    ["Sets the", "تنظیم"], ["Defines the", "تعریف"], ["Chooses", "انتخاب"], ["Number of", "تعداد"],
    ["Maximum", "حداکثر"], ["Minimum", "حداقل"], ["Fraction", "سهم"], ["Enables", "فعال‌سازی"],
    ["Initial", "ابتدایی"], ["Final", "نهایی"], ["External", "خارجی"], ["Generation", "نسل"],
    ["structure", "ساختار"], ["structures", "ساختارها"], ["relaxation", "ریلکسیشن"], ["symmetry", "تقارن"],
  ],
  hi: [
    ["Sets the", "सेट करता है"], ["Defines the", "परिभाषित करता है"], ["Chooses", "चुनता है"], ["Number of", "संख्या"],
    ["Maximum", "अधिकतम"], ["Minimum", "न्यूनतम"], ["Fraction", "अनुपात"], ["Enables", "सक्रिय करता है"],
    ["Initial", "प्रारंभिक"], ["Final", "अंतिम"], ["External", "बाहरी"], ["Generation", "पीढ़ी"],
    ["structure", "संरचना"], ["structures", "संरचनाएँ"], ["relaxation", "रिलैक्सेशन"], ["symmetry", "सममिति"],
  ],
};
const ADV_DEFAULTS = {
  populationSize: "80",
  initialPopSize: "200",
  numGenerations: "60",
  stopCrit: "20",
};
const UI_TRANSLATIONS = {
  ru: {
    hero_title: "USPEX Runner",
    hero_subtitle: "Crystal Discovery Starts Here",
    theme_label: "Тема",
    lang_label: "Язык",
    paths_title: "Пути",
    path_uspex: "Путь к uspex.exe",
    path_stmng: "Путь к STMng.exe",
    workdir: "Рабочая папка",
    mode_title: "Режим",
    advanced_settings: "Расширенные настройки",
    elements_formulas: "Элементы/формулы",
    counts_fixed: "Количество (fixed)",
    ratios_single: "Соотношения (single)",
    input_preview: "INPUT preview",
    preview_reset: "Вернуть согласно параметрам",
    enable_seeds: "Включить Seeds",
    enable_antiseeds: "Включить AntiSeeds",
    check_structures: "Проверить структуры",
    add_btn: "Добавить",
    check_hint: "Нажмите \"Проверить структуры\" для сводки.",
    materials_project: "Materials Project",
    api_key: "API ключ",
    system_label: "Система",
    energy_above_hull: "Energy Above Hull",
    add_to_seeds: "Добавить в Seeds",
    add_to_antiseeds: "Добавить в AntiSeeds",
    preview_results: "Предв. результаты",
    file_browser: "Браузер файлов",
    root_folder: "Корневая папка",
    current_folder: "Текущая папка",
    open_btn: "Открыть",
    root_btn: "Корень",
    folders: "Папки",
    files: "Файлы",
    opened_file: "Открытый файл",
    run_title: "Запуск",
    boom_btn: "Бум",
    run_btn: "Запуск",
    stop_btn: "Стоп",
    no_results: "Результаты Calculation не найдены.",
    add_to_generation: "Добавить в поколение",
    structure_label: "Структура",
    structures_word: "структур",
    elements_word: "элементы",
    reset_generations: "Сброс поколений",
    copy_structure_title: "Копировать структуру",
    open_file: "Открыть",
    hide_file: "Скрыть",
    view_btn: "Посмотреть",
    check_btn: "Проверить",
    to_seeds_btn: "В Seeds!",
    to_antiseeds_btn: "В AntiSeeds!",
    done: "Готово.",
    done_short: "Готово!",
    mining_structures: "Добываем структуры",
    checked: "Проверено.",
    seed_added: "Файл Seeds добавлен.",
    antiseed_added: "Файл AntiSeeds добавлен.",
    mp_seed_added: "MP seeds добавлены.",
    mp_antiseed_added: "MP anti-seeds добавлены.",
    specific_title: "Specific",
    specific_use_custom: "Использовать кастомный Specific",
    specific_add_defaults: "Добавить default Specific",
    specific_add_file: "Добавить файл",
    specific_editing_file: "Редактирование файла",
    specific_confirm_add_from_workdir: "В рабочей директории уже есть папка Specific. Добавить файлы оттуда к текущему списку?",
    specific_confirm_replace_from_workdir: "В рабочей директории уже есть папка Specific. Загрузить файлы оттуда вместо default Specific?",
    specific_description: "Папка Specific/ — это поддиректория (обычно располагающаяся по пути ~/StructurePrediction/Specific/), в которой хранятся все необходимые входные файлы для работы внешних вычислительных кодов (таких как VASP, SIESTA, GULP, ORCA и др.), которые USPEX использует для расчета энергии и релаксации (оптимизации) генерируемых структур.",
    run_started: "Запуск начат.",
    stop_sent: "Сигнал остановки отправлен.",
    browser_refreshed: "Браузер обновлён.",
    file_opened: "Файл открыт.",
    structure_copied: "Структура скопирована.",
    file_copied: "Содержимое файла скопировано.",
    stage_label: "Стадия",
    copy_file_title: "Копировать содержимое",
    status_prefix: "Статус",
    lang_ru: "🇷🇺 Русский",
    lang_en: "🌐 Английский",
    lang_zh: "🇨🇳 Китайский",
    lang_fa: "🇮🇷 Персидский",
    lang_hi: "🇮🇳 Хинди",
    mode_fixed: "Фиксированный состав",
    mode_single: "Одиночный блок",
    mode_variable: "Переменный состав",
    preview_dirty_hint: "Определяющим является текст в данном окне.",
    poscar_path: "POSCAR/POSCARS path",
    poscar_hint_seed: "Путь к локальному POSCAR/POSCARS файлу с одной или несколькими структурами для проверки и добавления в Seeds.",
    poscar_hint_anti: "Путь к локальному POSCAR/POSCARS файлу с одной или несколькими структурами для проверки и добавления в AntiSeeds.",
    system_hint: "Используйте символы элементов через дефис, например Fe-O или Li-Fe-O.",
    collapse_expand_title: "Свернуть/развернуть",
    up_title: "Вверх",
    adv_tip_prefix: "Описание параметра",
    adv_help_aria: "Описание параметра",
    status_idle: "Статус: idle",
    vault_prefix: "Get tired of discovering new materials? Have rest in our",
    vault_link: "Crystal Vault",
    vault_suffix: "!",
    stmng_installed: "STMng: установлен",
    stmng_missing: "STMng не найден по пути",
    stmng_install_hint: "Установите STMng для использования визуализации.",
    visualizer_running: "Visualizer STMng is Running!",
    run_confirm_title: "Запустить USPEX?",
    run_confirm_proceed: "Запустить",
    run_cancel: "Отмена",
    mkdir_prompt: "Имя новой папки:",
    ctx_rename: "Переименовать",
    ctx_set_workdir: "Сделать рабочей папкой",
    rename_prompt: "Новое имя:",
    prompt_ok: "ОК",
  },
  en: {
    hero_title: "USPEX Runner",
    hero_subtitle: "Crystal Discovery Starts Here",
    theme_label: "Theme",
    lang_label: "Language",
    paths_title: "Paths",
    path_uspex: "Path to uspex.exe",
    path_stmng: "Path to STMng.exe",
    workdir: "Workdir",
    mode_title: "Mode",
    advanced_settings: "Advanced settings",
    elements_formulas: "Elements/formulas",
    counts_fixed: "Counts (fixed)",
    ratios_single: "Ratios (single)",
    input_preview: "INPUT preview",
    preview_reset: "Reset to parameter-based",
    enable_seeds: "Enable Seeds",
    enable_antiseeds: "Enable AntiSeeds",
    check_structures: "Check Structures",
    add_btn: "Add",
    check_hint: "Press \"Check Structures\" to see summary.",
    materials_project: "Materials Project",
    api_key: "API key",
    system_label: "System",
    energy_above_hull: "Energy Above Hull",
    add_to_seeds: "Add to Seeds",
    add_to_antiseeds: "Add to AntiSeeds",
    preview_results: "Preview Results",
    file_browser: "File Browser",
    root_folder: "Root folder",
    current_folder: "Current folder",
    open_btn: "Open",
    root_btn: "Root",
    folders: "Folders",
    files: "Files",
    opened_file: "Opened file",
    run_title: "Run",
    boom_btn: "Boom",
    run_btn: "Run",
    stop_btn: "Stop",
    no_results: "No Calculation results found.",
    add_to_generation: "Add to generation",
    structure_label: "Structure",
    structures_word: "structures",
    elements_word: "elements",
    reset_generations: "Reset generations",
    copy_structure_title: "Copy structure",
    open_file: "Open",
    hide_file: "Hide",
    view_btn: "View",
    check_btn: "Check",
    to_seeds_btn: "To Seeds!",
    to_antiseeds_btn: "To AntiSeeds!",
    done: "Done.",
    done_short: "Done!",
    mining_structures: "Fetching structures",
    checked: "Checked.",
    seed_added: "Seed file added.",
    antiseed_added: "AntiSeed file added.",
    mp_seed_added: "MP seeds added.",
    mp_antiseed_added: "MP anti-seeds added.",
    specific_title: "Specific",
    specific_use_custom: "Use custom Specific",
    specific_add_defaults: "Add default Specific",
    specific_add_file: "Add file",
    specific_editing_file: "Editing file",
    specific_confirm_add_from_workdir: "Specific folder already exists in the selected workdir. Add files from it to the current list?",
    specific_confirm_replace_from_workdir: "Specific folder already exists in the selected workdir. Load files from it instead of default Specific?",
    specific_description: "The Specific/ folder is a subdirectory (usually at ~/StructurePrediction/Specific/) that stores all required input files for external computational codes (such as VASP, SIESTA, GULP, ORCA, etc.) that USPEX uses to calculate energies and relax (optimize) generated structures.",
    run_started: "Run started.",
    stop_sent: "Stop sent.",
    browser_refreshed: "Browser refreshed.",
    file_opened: "File opened.",
    structure_copied: "Structure copied.",
    file_copied: "File content copied.",
    stage_label: "Stage",
    copy_file_title: "Copy content",
    status_prefix: "Status",
    lang_ru: "🇷🇺 Russian",
    lang_en: "🌐 English",
    lang_zh: "🇨🇳 Chinese",
    lang_fa: "🇮🇷 Persian",
    lang_hi: "🇮🇳 Hindi",
    mode_fixed: "Fixed composition",
    mode_single: "Single block",
    mode_variable: "Variable composition",
    preview_dirty_hint: "Text in this window is the source of truth.",
    poscar_path: "POSCAR/POSCARS path",
    poscar_hint_seed: "Path to a local POSCAR/POSCARS file with one or multiple structures to validate and add into Seeds.",
    poscar_hint_anti: "Path to a local POSCAR/POSCARS file with one or multiple structures to validate and add into AntiSeeds.",
    system_hint: "Use element symbols separated by hyphens, e.g. Fe-O or Li-Fe-O.",
    collapse_expand_title: "Collapse/Expand",
    up_title: "Up",
    adv_tip_prefix: "Parameter description",
    adv_help_aria: "Parameter description",
    status_idle: "Status: idle",
    vault_prefix: "Get tired of discovering new materials? Have rest in our",
    vault_link: "Crystal Vault",
    vault_suffix: "!",
    stmng_installed: "STMng: installed",
    stmng_missing: "STMng not found at",
    stmng_install_hint: "Install STMng to use visualization.",
    visualizer_running: "Visualizer STMng is Running!",
    run_confirm_title: "Ready to run USPEX?",
    run_confirm_proceed: "Run",
    run_cancel: "Cancel",
    mkdir_prompt: "New folder name:",
    ctx_rename: "Rename",
    ctx_set_workdir: "Set as working folder",
    rename_prompt: "New name:",
    prompt_ok: "OK",
  },
  zh: {
    hero_title: "USPEX Runner",
    hero_subtitle: "Crystal Discovery Starts Here",
    theme_label: "主题",
    lang_label: "语言",
    paths_title: "路径",
    path_uspex: "uspex.exe 路径",
    path_stmng: "STMng.exe 路径",
    workdir: "工作目录",
    mode_title: "模式",
    advanced_settings: "高级设置",
    elements_formulas: "元素/化学式",
    counts_fixed: "数量 (fixed)",
    ratios_single: "比例 (single)",
    input_preview: "INPUT 预览",
    preview_reset: "恢复为参数生成",
    enable_seeds: "启用 Seeds",
    enable_antiseeds: "启用 AntiSeeds",
    check_structures: "检查结构",
    add_btn: "添加",
    check_hint: "点击“检查结构”查看摘要。",
    materials_project: "Materials Project",
    api_key: "API 密钥",
    system_label: "体系",
    energy_above_hull: "Energy Above Hull",
    add_to_seeds: "添加到 Seeds",
    add_to_antiseeds: "添加到 AntiSeeds",
    preview_results: "结果预览",
    file_browser: "文件浏览器",
    root_folder: "根目录",
    current_folder: "当前目录",
    open_btn: "打开",
    root_btn: "根目录",
    folders: "文件夹",
    files: "文件",
    opened_file: "已打开文件",
    run_title: "运行",
    boom_btn: "波浪",
    run_btn: "运行",
    stop_btn: "停止",
    no_results: "未找到 Calculation 结果。",
    add_to_generation: "添加到代",
    structure_label: "结构",
    structures_word: "个结构",
    elements_word: "元素",
    reset_generations: "重置代数",
    copy_structure_title: "复制结构",
    open_file: "打开",
    hide_file: "隐藏",
    view_btn: "查看",
    check_btn: "检查",
    to_seeds_btn: "到 Seeds!",
    to_antiseeds_btn: "到 AntiSeeds!",
    done: "完成。",
    done_short: "完成！",
    mining_structures: "正在获取结构",
    checked: "已检查。",
    seed_added: "Seeds 文件已添加。",
    antiseed_added: "AntiSeeds 文件已添加。",
    mp_seed_added: "已添加 MP seeds。",
    mp_antiseed_added: "已添加 MP anti-seeds。",
    specific_title: "Specific",
    specific_use_custom: "使用自定义 Specific",
    specific_add_defaults: "添加默认 Specific",
    specific_add_file: "添加文件",
    specific_editing_file: "编辑文件",
    specific_confirm_add_from_workdir: "所选工作目录中已存在 Specific 文件夹。是否将其中的文件添加到当前列表？",
    specific_confirm_replace_from_workdir: "所选工作目录中已存在 Specific 文件夹。是否从中加载文件以替代默认 Specific？",
    specific_description: "Specific/ 文件夹是一个子目录（通常位于 ~/StructurePrediction/Specific/），用于存放外部计算程序（如 VASP、SIESTA、GULP、ORCA 等）运行所需的输入文件。USPEX 会使用这些文件来计算能量并对生成结构进行弛豫（优化）。",
    run_started: "已开始运行。",
    stop_sent: "已发送停止信号。",
    browser_refreshed: "浏览器已刷新。",
    file_opened: "文件已打开。",
    structure_copied: "结构已复制。",
    file_copied: "文件内容已复制。",
    stage_label: "阶段",
    copy_file_title: "复制内容",
    status_prefix: "状态",
    lang_ru: "🇷🇺 俄语",
    lang_en: "🌐 英语",
    lang_zh: "🇨🇳 中文",
    lang_fa: "🇮🇷 波斯语",
    lang_hi: "🇮🇳 印地语",
    mode_fixed: "固定组成",
    mode_single: "单块",
    mode_variable: "可变组成",
    preview_dirty_hint: "此窗口中的文本为最终依据。",
    poscar_path: "POSCAR/POSCARS 路径",
    poscar_hint_seed: "本地 POSCAR/POSCARS 文件路径，可包含一个或多个结构，用于检查并添加到 Seeds。",
    poscar_hint_anti: "本地 POSCAR/POSCARS 文件路径，可包含一个或多个结构，用于检查并添加到 AntiSeeds。",
    system_hint: "使用连字符分隔元素符号，例如 Fe-O 或 Li-Fe-O。",
    collapse_expand_title: "折叠/展开",
    up_title: "向上",
    adv_tip_prefix: "参数说明",
    adv_help_aria: "参数说明",
    status_idle: "状态: idle",
    vault_prefix: "Get tired of discovering new materials? Have rest in our",
    vault_link: "Crystal Vault",
    vault_suffix: "!",
    stmng_installed: "STMng: 已安装",
    stmng_missing: "未在此路径找到 STMng",
    stmng_install_hint: "请安装 STMng 以使用可视化。",
    visualizer_running: "Visualizer STMng is Running!",
    run_confirm_title: "准备运行 USPEX？",
    run_confirm_proceed: "运行",
    run_cancel: "取消",
    mkdir_prompt: "新文件夹名称：",
    ctx_rename: "重命名",
    ctx_set_workdir: "设为工作目录",
    rename_prompt: "新名称：",
    prompt_ok: "确定",
  },
  fa: {
    hero_title: "USPEX Runner",
    hero_subtitle: "Crystal Discovery Starts Here",
    theme_label: "تم",
    lang_label: "زبان",
    paths_title: "مسیرها",
    path_uspex: "مسیر uspex.exe",
    path_stmng: "مسیر STMng.exe",
    workdir: "پوشه کاری",
    mode_title: "حالت",
    advanced_settings: "تنظیمات پیشرفته",
    elements_formulas: "عناصر/فرمول‌ها",
    counts_fixed: "تعداد (fixed)",
    ratios_single: "نسبت‌ها (single)",
    input_preview: "پیش‌نمایش INPUT",
    preview_reset: "بازگردانی بر اساس پارامترها",
    enable_seeds: "فعال‌سازی Seeds",
    enable_antiseeds: "فعال‌سازی AntiSeeds",
    check_structures: "بررسی ساختارها",
    add_btn: "افزودن",
    check_hint: "برای خلاصه روی «بررسی ساختارها» بزنید.",
    materials_project: "Materials Project",
    api_key: "کلید API",
    system_label: "سیستم",
    energy_above_hull: "Energy Above Hull",
    add_to_seeds: "افزودن به Seeds",
    add_to_antiseeds: "افزودن به AntiSeeds",
    preview_results: "پیش‌نمایش نتایج",
    file_browser: "مرورگر فایل",
    root_folder: "پوشه ریشه",
    current_folder: "پوشه فعلی",
    open_btn: "باز کردن",
    root_btn: "ریشه",
    folders: "پوشه‌ها",
    files: "فایل‌ها",
    opened_file: "فایل بازشده",
    run_title: "اجرا",
    boom_btn: "موج",
    run_btn: "اجرا",
    stop_btn: "توقف",
    no_results: "نتیجه‌ای در Calculation پیدا نشد.",
    add_to_generation: "افزودن به نسل",
    structure_label: "ساختار",
    structures_word: "ساختار",
    elements_word: "عناصر",
    reset_generations: "بازنشانی نسل‌ها",
    copy_structure_title: "کپی ساختار",
    open_file: "باز کردن",
    hide_file: "پنهان کردن",
    view_btn: "نمایش",
    check_btn: "بررسی",
    to_seeds_btn: "به Seeds!",
    to_antiseeds_btn: "به AntiSeeds!",
    done: "انجام شد.",
    done_short: "انجام شد!",
    mining_structures: "در حال دریافت ساختارها",
    checked: "بررسی شد.",
    seed_added: "فایل Seeds اضافه شد.",
    antiseed_added: "فایل AntiSeeds اضافه شد.",
    mp_seed_added: "MP seeds اضافه شد.",
    mp_antiseed_added: "MP anti-seeds اضافه شد.",
    specific_title: "Specific",
    specific_use_custom: "استفاده از Specific سفارشی",
    specific_add_defaults: "افزودن default Specific",
    specific_add_file: "افزودن فایل",
    specific_editing_file: "ویرایش فایل",
    specific_confirm_add_from_workdir: "پوشه Specific در مسیر کاری انتخاب‌شده وجود دارد. فایل‌های آن به فهرست فعلی اضافه شوند؟",
    specific_confirm_replace_from_workdir: "پوشه Specific در مسیر کاری انتخاب‌شده وجود دارد. فایل‌های آن به‌جای default Specific بارگذاری شوند؟",
    specific_description: "پوشه Specific/ یک زیردایرکتوری است (معمولاً در مسیر ~/StructurePrediction/Specific/) که همه فایل‌های ورودی لازم برای کدهای محاسباتی خارجی (مانند VASP، SIESTA، GULP، ORCA و غیره) را نگه می‌دارد؛ کدهایی که USPEX برای محاسبه انرژی و ریلکس‌کردن (بهینه‌سازی) ساختارهای تولیدشده از آن‌ها استفاده می‌کند.",
    run_started: "اجرا شروع شد.",
    stop_sent: "دستور توقف ارسال شد.",
    browser_refreshed: "مرورگر به‌روزرسانی شد.",
    file_opened: "فایل باز شد.",
    structure_copied: "ساختار کپی شد.",
    file_copied: "محتوای فایل کپی شد.",
    stage_label: "مرحله",
    copy_file_title: "کپی محتوا",
    status_prefix: "وضعیت",
    lang_ru: "🇷🇺 روسی",
    lang_en: "🌐 انگلیسی",
    lang_zh: "🇨🇳 چینی",
    lang_fa: "🇮🇷 فارسی",
    lang_hi: "🇮🇳 هندی",
    mode_fixed: "ترکیب ثابت",
    mode_single: "بلوک تکی",
    mode_variable: "ترکیب متغیر",
    preview_dirty_hint: "متن این پنجره مرجع نهایی است.",
    poscar_path: "مسیر POSCAR/POSCARS",
    poscar_hint_seed: "مسیر فایل محلی POSCAR/POSCARS با یک یا چند ساختار برای بررسی و افزودن به Seeds.",
    poscar_hint_anti: "مسیر فایل محلی POSCAR/POSCARS با یک یا چند ساختار برای بررسی و افزودن به AntiSeeds.",
    system_hint: "نماد عناصر را با خط تیره وارد کنید، مانند Fe-O یا Li-Fe-O.",
    collapse_expand_title: "جمع/باز کردن",
    up_title: "بالا",
    adv_tip_prefix: "توضیح پارامتر",
    adv_help_aria: "توضیح پارامتر",
    status_idle: "وضعیت: idle",
    vault_prefix: "Get tired of discovering new materials? Have rest in our",
    vault_link: "Crystal Vault",
    vault_suffix: "!",
    stmng_installed: "STMng: نصب شده",
    stmng_missing: "STMng در این مسیر پیدا نشد",
    stmng_install_hint: "برای استفاده از بصری‌سازی STMng را نصب کنید.",
    visualizer_running: "Visualizer STMng is Running!",
    run_confirm_title: "آماده اجرای USPEX؟",
    run_confirm_proceed: "اجرا",
    run_cancel: "لغو",
    mkdir_prompt: "نام پوشه جدید:",
    ctx_rename: "تغییر نام",
    ctx_set_workdir: "تعیین به عنوان پوشه کاری",
    rename_prompt: "نام جدید:",
    prompt_ok: "تأیید",
  },
  hi: {
    hero_title: "USPEX Runner",
    hero_subtitle: "Crystal Discovery Starts Here",
    theme_label: "थीम",
    lang_label: "भाषा",
    paths_title: "पाथ्स",
    path_uspex: "uspex.exe का पाथ",
    path_stmng: "STMng.exe का पाथ",
    workdir: "वर्कडिर",
    mode_title: "मोड",
    advanced_settings: "एडवांस्ड सेटिंग्स",
    elements_formulas: "एलिमेंट्स/फॉर्मुलाज़",
    counts_fixed: "काउंट्स (fixed)",
    ratios_single: "रेशियो (single)",
    input_preview: "INPUT प्रीव्यू",
    preview_reset: "पैरामीटर के अनुसार रीसेट",
    enable_seeds: "Seeds सक्षम करें",
    enable_antiseeds: "AntiSeeds सक्षम करें",
    check_structures: "स्ट्रक्चर जाँचें",
    add_btn: "जोड़ें",
    check_hint: "सारांश देखने के लिए \"Check Structures\" दबाएँ।",
    materials_project: "Materials Project",
    api_key: "API कुंजी",
    system_label: "सिस्टम",
    energy_above_hull: "Energy Above Hull",
    add_to_seeds: "Seeds में जोड़ें",
    add_to_antiseeds: "AntiSeeds में जोड़ें",
    preview_results: "प्रीव्यू परिणाम",
    file_browser: "फ़ाइल ब्राउज़र",
    root_folder: "रूट फ़ोल्डर",
    current_folder: "वर्तमान फ़ोल्डर",
    open_btn: "खोलें",
    root_btn: "रूट",
    folders: "फ़ोल्डर्स",
    files: "फ़ाइलें",
    opened_file: "खोली गई फ़ाइल",
    run_title: "रन",
    boom_btn: "लहर",
    run_btn: "रन",
    stop_btn: "स्टॉप",
    no_results: "कोई Calculation परिणाम नहीं मिला।",
    add_to_generation: "जनरेशन में जोड़ें",
    structure_label: "संरचना",
    structures_word: "संरचनाएँ",
    elements_word: "तत्व",
    reset_generations: "जनरेशन रीसेट",
    copy_structure_title: "संरचना कॉपी करें",
    open_file: "खोलें",
    hide_file: "छिपाएँ",
    view_btn: "देखें",
    check_btn: "जाँचें",
    to_seeds_btn: "Seeds में!",
    to_antiseeds_btn: "AntiSeeds में!",
    done: "हो गया।",
    done_short: "हो गया!",
    mining_structures: "संरचनाएँ प्राप्त कर रहे हैं",
    checked: "जाँच हो गई।",
    seed_added: "Seeds फ़ाइल जोड़ दी गई।",
    antiseed_added: "AntiSeeds फ़ाइल जोड़ दी गई।",
    mp_seed_added: "MP seeds जोड़ दिए गए।",
    mp_antiseed_added: "MP anti-seeds जोड़ दिए गए।",
    specific_title: "Specific",
    specific_use_custom: "कस्टम Specific उपयोग करें",
    specific_add_defaults: "डिफ़ॉल्ट Specific जोड़ें",
    specific_add_file: "फ़ाइल जोड़ें",
    specific_editing_file: "फ़ाइल संपादन",
    specific_confirm_add_from_workdir: "चयनित workdir में Specific फ़ोल्डर पहले से मौजूद है। क्या वहाँ से फ़ाइलें मौजूदा सूची में जोड़ें?",
    specific_confirm_replace_from_workdir: "चयनित workdir में Specific फ़ोल्डर पहले से मौजूद है। क्या default Specific के बजाय वहाँ से फ़ाइलें लोड करें?",
    specific_description: "Specific/ फ़ोल्डर एक सबडायरेक्टरी है (आमतौर पर ~/StructurePrediction/Specific/ पर), जिसमें बाहरी गणनात्मक कोड (जैसे VASP, SIESTA, GULP, ORCA आदि) के लिए आवश्यक सभी इनपुट फ़ाइलें रखी जाती हैं। USPEX इन्हीं फ़ाइलों का उपयोग जनरेटेड संरचनाओं की ऊर्जा गणना और रिलैक्सेशन (ऑप्टिमाइज़ेशन) के लिए करता है।",
    run_started: "रन शुरू हुआ।",
    stop_sent: "स्टॉप सिग्नल भेजा गया।",
    browser_refreshed: "ब्राउज़र रीफ़्रेश हुआ।",
    file_opened: "फ़ाइल खुल गई।",
    structure_copied: "संरचना कॉपी हो गई।",
    file_copied: "फ़ाइल कंटेंट कॉपी हो गया।",
    stage_label: "स्टेज",
    copy_file_title: "सामग्री कॉपी करें",
    status_prefix: "स्थिति",
    lang_ru: "🇷🇺 रूसी",
    lang_en: "🌐 अंग्रेज़ी",
    lang_zh: "🇨🇳 चीनी",
    lang_fa: "🇮🇷 फ़ारसी",
    lang_hi: "🇮🇳 हिन्दी",
    mode_fixed: "निश्चित संरचना",
    mode_single: "सिंगल ब्लॉक",
    mode_variable: "परिवर्ती संरचना",
    preview_dirty_hint: "इस विंडो का टेक्स्ट ही अंतिम मान्य टेक्स्ट है।",
    poscar_path: "POSCAR/POSCARS पाथ",
    poscar_hint_seed: "लोकल POSCAR/POSCARS फ़ाइल का पाथ, जिसमें एक या अधिक स्ट्रक्चर हों, उन्हें जाँचकर Seeds में जोड़ने के लिए।",
    poscar_hint_anti: "लोकल POSCAR/POSCARS फ़ाइल का पाथ, जिसमें एक या अधिक स्ट्रक्चर हों, उन्हें जाँचकर AntiSeeds में जोड़ने के लिए।",
    system_hint: "एलिमेंट सिंबल को हाइफ़न से अलग करके लिखें, जैसे Fe-O या Li-Fe-O।",
    collapse_expand_title: "समेटें/फैलाएँ",
    up_title: "ऊपर",
    adv_tip_prefix: "पैरामीटर विवरण",
    adv_help_aria: "पैरामीटर विवरण",
    status_idle: "स्थिति: idle",
    vault_prefix: "Get tired of discovering new materials? Have rest in our",
    vault_link: "Crystal Vault",
    vault_suffix: "!",
    stmng_installed: "STMng: इंस्टॉल है",
    stmng_missing: "STMng इस पाथ पर नहीं मिला",
    stmng_install_hint: "विज़ुअलाइज़ेशन के लिए STMng इंस्टॉल करें।",
    visualizer_running: "Visualizer STMng is Running!",
    run_confirm_title: "USPEX चलाएँ?",
    run_confirm_proceed: "चलाएँ",
    run_cancel: "रद्द करें",
    mkdir_prompt: "नए फ़ोल्डर का नाम:",
    ctx_rename: "नाम बदलें",
    ctx_set_workdir: "कार्य फ़ोल्डर के रूप में सेट करें",
    rename_prompt: "नया नाम:",
    prompt_ok: "ठीक है",
  },
};
let currentUiTheme = "Ocean";
const modeCache = {
  fixed: { elements_text: "Si O", counts_text: "6 12", ratios_text: "1 2", min_at_text: "8", max_at_text: "18", advanced_enabled: false, advanced_params: {}, preview_text: "", preview_dirty: false },
  single: { elements_text: "Si O", counts_text: "6 12", ratios_text: "1 2", min_at_text: "8", max_at_text: "18", advanced_enabled: false, advanced_params: {}, preview_text: "", preview_dirty: false },
  variable: { elements_text: "Si O", counts_text: "6 12", ratios_text: "1 2", min_at_text: "8", max_at_text: "18", advanced_enabled: false, advanced_params: {}, preview_text: "", preview_dirty: false },
};

function flash(text, ok = true) {
  const el = document.getElementById("flash");
  el.textContent = text || "";
  el.style.color = ok ? "#126b2e" : "#9b1d37";
}

function hexToRgb(hex) {
  const raw = String(hex || "").trim().replace("#", "");
  if (!/^[0-9a-fA-F]{6}$/.test(raw)) return null;
  return {
    r: parseInt(raw.slice(0, 2), 16),
    g: parseInt(raw.slice(2, 4), 16),
    b: parseInt(raw.slice(4, 6), 16),
  };
}

function mixHex(hexA, hexB, t) {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  if (!a || !b) return hexA;
  const clamped = Math.max(0, Math.min(1, Number(t)));
  const r = Math.round(a.r + (b.r - a.r) * clamped);
  const g = Math.round(a.g + (b.g - a.g) * clamped);
  const bl = Math.round(a.b + (b.b - a.b) * clamped);
  const toHex = (v) => v.toString(16).padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(bl)}`;
}

function applyTheme(theme) {
  const picked = UI_THEMES.find((x) => x.name === theme) || UI_THEMES[0];
  currentUiTheme = picked.name;
  currentThemePalette = { primary: picked.primary, bg: picked.bg, text: picked.text };
  const root = document.documentElement.style;
  const accent2 = mixHex(picked.primary, "#ffffff", 0.22);
  const accentSoft = mixHex(picked.primary, "#ffffff", 0.84);
  root.setProperty("--accent", picked.primary);
  root.setProperty("--accent-2", accent2);
  root.setProperty("--accent-soft", accentSoft);
  root.setProperty("--bg-a", picked.bg);
  root.setProperty("--bg-b", picked.bg);
  root.setProperty("--ink", picked.text);
  root.setProperty("--panel", mixHex(picked.bg, "#ffffff", 0.62));
  root.setProperty("--line", mixHex(picked.primary, "#ffffff", 0.74));
  root.setProperty("--muted", mixHex(picked.text, picked.primary, 0.28));
  root.setProperty("--danger", "#be2d5a");
  root.setProperty("--danger-soft", "#fff0f5");
  root.setProperty("--hero-ink", "#ffffff");
  root.setProperty("--effect-btn-bg", picked.primary);
  root.setProperty("--effect-btn-border", picked.primary);
  root.setProperty("--effect-btn-text", "#ffffff");
  root.setProperty("--effect-clean-bg", "#ffffff");
  root.setProperty("--effect-clean-border", picked.primary);
  root.setProperty("--effect-clean-text", picked.text);
  if (picked.name === "White Linen") {
    root.setProperty("--hero-ink", "#111111");
  }
  if (picked.name === "Pink Bloom") {
    document.body.style.background =
      "radial-gradient(circle at 10% 10%, #ffffff, transparent 40%)," +
      "radial-gradient(circle at 85% 20%, #ffd9ec, transparent 35%)," +
      "linear-gradient(180deg, #fff1f8, #ffe7f3)";
  } else {
    document.body.style.background =
      "radial-gradient(circle at 10% 10%, #ffffff, transparent 40%)," +
      "radial-gradient(circle at 85% 20%, #dbe9fb, transparent 35%)," +
      "linear-gradient(180deg, var(--bg-a), var(--bg-b))";
  }
  if (picked.name === "Pink Bloom") {
    cleanupSunsetEffect();
    cleanupWaveEffect();
    updateBoomButtons();
  } else if (picked.name === "Sunset") {
    cleanupBoomEffect();
    cleanupWaveEffect();
    updateBoomButtons();
  } else if (picked.name === "Deep Blue") {
    cleanupBoomEffect();
    cleanupSunsetEffect();
    updateBoomButtons();
  } else {
    cleanupBoomEffect();
    cleanupSunsetEffect();
    cleanupWaveEffect();
  }
}

function applyLanguage(lang) {
  const effective = UI_TRANSLATIONS[lang] ? lang : "ru";
  const t = UI_TRANSLATIONS[effective];
  document.documentElement.lang = effective;
  document.documentElement.dir = effective === "fa" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.dataset.i18n;
    if (key && t[key]) el.textContent = t[key];
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    const key = el.dataset.i18nTitle;
    if (key && t[key]) el.setAttribute("title", t[key]);
  });
  const themeSelect = document.getElementById("ui_theme");
  if (themeSelect) themeSelect.setAttribute("title", t.theme_label);
  const langSelect = document.getElementById("ui_lang");
  if (langSelect) {
    const optRu = langSelect.querySelector('option[value="ru"]');
    const optEn = langSelect.querySelector('option[value="en"]');
    const optZh = langSelect.querySelector('option[value="zh"]');
    const optFa = langSelect.querySelector('option[value="fa"]');
    const optHi = langSelect.querySelector('option[value="hi"]');
    if (optRu) optRu.textContent = t.lang_ru;
    if (optEn) optEn.textContent = t.lang_en;
    if (optZh) optZh.textContent = t.lang_zh;
    if (optFa) optFa.textContent = t.lang_fa;
    if (optHi) optHi.textContent = t.lang_hi;
  }
  updateAdvancedLocalizedTexts();
  if (isSpecificModalOpen()) {
    renderSpecificModal();
  }
}

function currentLang() {
  const sel = document.getElementById("ui_lang");
  const lang = sel?.value || localStorage.getItem(UI_LANG_STORAGE_KEY) || "ru";
  return UI_TRANSLATIONS[lang] ? lang : "ru";
}

function tr(key) {
  const lang = currentLang();
  return UI_TRANSLATIONS[lang]?.[key]
    || UI_TRANSLATIONS.en?.[key]
    || UI_TRANSLATIONS.ru?.[key]
    || key;
}

function setMpStatus(which, phase) {
  const id = which === "anti" ? "anti_seed_mp_status" : "seed_mp_status";
  const el = document.getElementById(id);
  if (!el) return;
  if (mpStatusTimers[id]) {
    clearTimeout(mpStatusTimers[id]);
    delete mpStatusTimers[id];
  }
  if (phase === "loading") {
    el.style.display = "inline-flex";
    el.classList.remove("done");
    const textEl = el.querySelector("span[data-i18n], span:last-child");
    if (textEl) textEl.textContent = tr("mining_structures");
    return;
  }
  if (phase === "done") {
    el.style.display = "inline-flex";
    el.classList.add("done");
    const textEl = el.querySelector("span[data-i18n], span:last-child");
    if (textEl) textEl.textContent = tr("done_short");
    mpStatusTimers[id] = setTimeout(() => {
      el.style.display = "none";
      el.classList.remove("done");
      const resetTextEl = el.querySelector("span[data-i18n], span:last-child");
      if (resetTextEl) resetTextEl.textContent = tr("mining_structures");
      delete mpStatusTimers[id];
    }, 1400);
    return;
  }
  el.style.display = "none";
  el.classList.remove("done");
  const textEl = el.querySelector("span[data-i18n], span:last-child");
  if (textEl) textEl.textContent = tr("mining_structures");
}

function advGroupTitle(index, fallbackTitle) {
  const lang = currentLang();
  const list = ADV_GROUP_TITLES[lang] || ADV_GROUP_TITLES.en;
  return list?.[index] || fallbackTitle;
}

function advTipText(field) {
  const lang = currentLang();
  if (lang === "en") return field.tip;
  const rules = ADV_TIP_RULES[lang];
  if (!rules || !rules.length) return field.tip;
  let out = field.tip;
  for (const [src, dst] of rules) {
    out = out.replaceAll(src, dst);
  }
  return out;
}

function updateAdvancedLocalizedTexts() {
  document.querySelectorAll("[data-adv-group]").forEach((el) => {
    const idx = Number(el.getAttribute("data-adv-group"));
    const fallback = ADV_GROUPS[idx]?.title || "";
    el.textContent = advGroupTitle(idx, fallback);
  });
  document.querySelectorAll(".help-tooltip[data-adv-tip]").forEach((el) => {
    const key = String(el.getAttribute("data-adv-tip") || "");
    const field = ADV_FIELD_BY_KEY[key];
    if (!field) return;
    el.textContent = advTipText(field);
  });
  document.querySelectorAll(".adv-param-key[data-adv-tip]").forEach((el) => {
    el.setAttribute("aria-label", tr("adv_help_aria"));
  });
}

function showTopToast(message) {
  let el = document.getElementById("top_toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "top_toast";
    el.className = "top-toast";
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.classList.add("show");
  if (topToastTimer) clearTimeout(topToastTimer);
  topToastTimer = setTimeout(() => {
    el.classList.remove("show");
  }, 2000);
}

function isThemeEffectEnabled(themeName) {
  return themeName === "Pink Bloom" || themeName === "Sunset" || themeName === "Deep Blue";
}

function ensureBoomOverlay() {
  let overlay = document.getElementById("boom_overlay");
  if (overlay) return overlay;
  overlay = document.createElement("div");
  overlay.id = "boom_overlay";
  overlay.innerHTML = `
    <div id="boom_hearts_layer"></div>
    <div id="boom_svg_mask_layer"></div>
  `;
  document.body.appendChild(overlay);
  return overlay;
}

function fillBoomHearts() {
  const heartsLayer = document.getElementById("boom_hearts_layer");
  if (!heartsLayer) return;
  heartsLayer.innerHTML = "";
  const area = window.innerWidth * window.innerHeight;
  const count = Math.max(300, Math.min(900, Math.round(area / 3400)));
  const colors = [
    mixHex(currentThemePalette.primary, "#ffffff", 0.05),
    mixHex(currentThemePalette.primary, "#ffffff", 0.2),
    mixHex(currentThemePalette.primary, "#ffffff", 0.35),
    mixHex(currentThemePalette.primary, "#000000", 0.08),
    mixHex(currentThemePalette.primary, currentThemePalette.bg, 0.25),
  ];
  const frag = document.createDocumentFragment();
  for (let i = 0; i < count; i++) {
    const heart = document.createElement("div");
    heart.className = "boom-heart";
    heart.textContent = "❤";
    const size = 20 + Math.random() * 18;
    const posX = Math.random() * window.innerWidth;
    const posY = Math.random() * window.innerHeight;
    heart.style.left = `${posX}px`;
    heart.style.top = `${posY}px`;
    heart.style.fontSize = `${size}px`;
    heart.style.color = colors[Math.floor(Math.random() * colors.length)];
    heart.style.transform = `rotate(${Math.random() * 24 - 12}deg)`;
    heart.style.animationDelay = `${Math.random() * 0.25}s`;
    frag.appendChild(heart);
  }
  heartsLayer.appendChild(frag);
}

function showBoomUSPEXCutout() {
  const svgMaskLayer = document.getElementById("boom_svg_mask_layer");
  if (!svgMaskLayer) return;
  const w = window.innerWidth;
  const h = window.innerHeight;
  const fontSize = Math.min(w * 0.22, h * 0.38, 240);
  const strokeWidth = Math.max(2, fontSize * 0.015);
  svgMaskLayer.innerHTML = `
    <svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <mask id="boom-text-hole-mask">
          <rect width="100%" height="100%" fill="white"></rect>
          <text
            x="50%"
            y="50%"
            text-anchor="middle"
            dominant-baseline="middle"
            font-size="${fontSize}"
            font-weight="900"
            font-family="Arial Black, Arial, sans-serif"
            letter-spacing="8"
            fill="black"
          >USPEX</text>
        </mask>
      </defs>
      <rect width="100%" height="100%" fill="${currentThemePalette.bg}" mask="url(#boom-text-hole-mask)"></rect>
      <text
        x="50%"
        y="50%"
        text-anchor="middle"
        dominant-baseline="middle"
        font-size="${fontSize}"
        font-weight="900"
        font-family="Arial Black, Arial, sans-serif"
        letter-spacing="8"
        fill="none"
        stroke="${mixHex(currentThemePalette.primary, "#ffffff", 0.55)}"
        stroke-width="${strokeWidth}"
      >USPEX</text>
    </svg>
  `;
  svgMaskLayer.classList.add("show");
}

function updateBoomButtons() {
  const controls = document.getElementById("boom_controls");
  const boomBtn = document.getElementById("boom_btn");
  if (!controls || !boomBtn) return;
  const effectTheme = isThemeEffectEnabled(currentUiTheme);
  controls.style.display = effectTheme ? "flex" : "none";
  if (!effectTheme) {
    boomBtn.style.display = "none";
    return;
  }
  const launched = currentUiTheme === "Sunset"
    ? sunsetLaunched
    : (currentUiTheme === "Deep Blue" ? waveLaunched : boomLaunched);
  boomBtn.style.display = launched ? "none" : "";
}

function runBoomEffect() {
  if (boomLaunched) return;
  boomLaunched = true;
  ensureBoomOverlay();
  const overlay = document.getElementById("boom_overlay");
  const heartsLayer = document.getElementById("boom_hearts_layer");
  const svgMaskLayer = document.getElementById("boom_svg_mask_layer");
  if (!overlay || !heartsLayer || !svgMaskLayer) return;
  overlay.classList.add("show");
  svgMaskLayer.classList.remove("show");
  svgMaskLayer.innerHTML = "";
  fillBoomHearts();
  heartsLayer.classList.add("show");
  if (boomFinishTimer) clearTimeout(boomFinishTimer);
  if (boomClearTimer) clearTimeout(boomClearTimer);
  boomFinishTimer = setTimeout(() => {
    showBoomUSPEXCutout();
    boomFinishTimer = setTimeout(() => {
      cleanupBoomEffect();
    }, 1400);
  }, 1200);
  updateBoomButtons();
}

function cleanupBoomEffect() {
  if (boomFinishTimer) {
    clearTimeout(boomFinishTimer);
    boomFinishTimer = null;
  }
  if (boomClearTimer) {
    clearTimeout(boomClearTimer);
    boomClearTimer = null;
  }
  boomLaunched = false;
  const overlay = document.getElementById("boom_overlay");
  const heartsLayer = document.getElementById("boom_hearts_layer");
  const svgMaskLayer = document.getElementById("boom_svg_mask_layer");
  if (overlay) {
    overlay.classList.remove("show");
  }
  boomClearTimer = setTimeout(() => {
    if (heartsLayer) {
      heartsLayer.classList.remove("show");
      heartsLayer.innerHTML = "";
    }
    if (svgMaskLayer) {
      svgMaskLayer.classList.remove("show");
      svgMaskLayer.innerHTML = "";
    }
    boomClearTimer = null;
  }, 2300);
  updateBoomButtons();
}

function ensureSunsetOverlay() {
  let overlay = document.getElementById("sunset_overlay");
  if (overlay) return overlay;
  overlay = document.createElement("div");
  overlay.id = "sunset_overlay";
  overlay.innerHTML = `
    <div id="sunset_sand_layer"></div>
    <div id="sunset_mask_layer"></div>
  `;
  document.body.appendChild(overlay);
  return overlay;
}

function randomSunsetSandColor() {
  const colors = [
    mixHex(currentThemePalette.primary, "#ffffff", 0.18),
    mixHex(currentThemePalette.primary, "#ffffff", 0.35),
    mixHex(currentThemePalette.primary, "#000000", 0.06),
    mixHex(currentThemePalette.primary, currentThemePalette.bg, 0.22),
    currentThemePalette.primary,
  ];
  return colors[Math.floor(Math.random() * colors.length)];
}

function fillSunsetSand() {
  const sandLayer = document.getElementById("sunset_sand_layer");
  if (!sandLayer) return;
  sandLayer.innerHTML = "";
  const area = window.innerWidth * window.innerHeight;
  const count = Math.max(260, Math.min(780, Math.round(area / 5200)));
  const frag = document.createDocumentFragment();
  for (let i = 0; i < count; i++) {
    const s = document.createElement("div");
    s.className = "sunset-sand";
    const size = Math.random() * 4 + 2;
    s.style.width = `${size}px`;
    s.style.height = `${size}px`;
    s.style.top = `${Math.random() * window.innerHeight}px`;
    s.style.left = `${Math.random() * window.innerWidth}px`;
    s.style.background = randomSunsetSandColor();
    s.style.animationDuration = `${2 + Math.random() * 3}s`;
    s.style.animationDelay = `${Math.random() * 2}s`;
    frag.appendChild(s);
  }
  sandLayer.appendChild(frag);
}

function showSunsetUSPEXCutout() {
  const maskLayer = document.getElementById("sunset_mask_layer");
  if (!maskLayer) return;
  const w = window.innerWidth;
  const h = window.innerHeight;
  const size = Math.min(w * 0.22, h * 0.35);
  maskLayer.innerHTML = `
    <svg width="${w}" height="${h}">
      <defs>
        <mask id="sunset-mask">
          <rect width="100%" height="100%" fill="white"></rect>
          <text
            x="50%"
            y="50%"
            text-anchor="middle"
            dominant-baseline="middle"
            font-size="${size}"
            font-weight="900"
            fill="black"
            font-family="Arial Black, Arial, sans-serif"
          >USPEX</text>
        </mask>
      </defs>
      <rect width="100%" height="100%" fill="${currentThemePalette.bg}" mask="url(#sunset-mask)"></rect>
    </svg>
  `;
  maskLayer.classList.add("show");
}

function runSunsetEffect() {
  if (sunsetLaunched) return;
  sunsetLaunched = true;
  ensureSunsetOverlay();
  const overlay = document.getElementById("sunset_overlay");
  const sandLayer = document.getElementById("sunset_sand_layer");
  const maskLayer = document.getElementById("sunset_mask_layer");
  if (!overlay || !sandLayer || !maskLayer) return;
  overlay.classList.add("show");
  maskLayer.classList.remove("show");
  maskLayer.innerHTML = "";
  fillSunsetSand();
  sandLayer.classList.add("show");
  if (sunsetFinishTimer) clearTimeout(sunsetFinishTimer);
  if (sunsetClearTimer) clearTimeout(sunsetClearTimer);
  sunsetFinishTimer = setTimeout(() => {
    showSunsetUSPEXCutout();
    sunsetFinishTimer = setTimeout(() => {
      cleanupSunsetEffect();
    }, 4200);
  }, 1500);
  updateBoomButtons();
}

function cleanupSunsetEffect() {
  if (sunsetFinishTimer) {
    clearTimeout(sunsetFinishTimer);
    sunsetFinishTimer = null;
  }
  if (sunsetClearTimer) {
    clearTimeout(sunsetClearTimer);
    sunsetClearTimer = null;
  }
  sunsetLaunched = false;
  const overlay = document.getElementById("sunset_overlay");
  const sandLayer = document.getElementById("sunset_sand_layer");
  const maskLayer = document.getElementById("sunset_mask_layer");
  if (overlay) overlay.classList.remove("show");
  sunsetClearTimer = setTimeout(() => {
    if (sandLayer) {
      sandLayer.classList.remove("show");
      sandLayer.innerHTML = "";
    }
    if (maskLayer) {
      maskLayer.classList.remove("show");
      maskLayer.innerHTML = "";
    }
    sunsetClearTimer = null;
  }, 2300);
  updateBoomButtons();
}

function ensureWaveOverlay() {
  let overlay = document.getElementById("wave_overlay");
  if (overlay) return overlay;
  overlay = document.createElement("div");
  overlay.id = "wave_overlay";
  overlay.innerHTML = `
    <div id="wave_small_layer"></div>
    <div id="wave_big_layer"><svg id="wave_big" viewBox="0 0 800 700" preserveAspectRatio="none" aria-hidden="true"></svg></div>
    <div id="wave_foam_layer"></div>
    <div id="wave_logo_layer"><div id="wave_logo_text">USPEX</div></div>
    <div id="wave_drips_layer"></div>
  `;
  document.body.appendChild(overlay);
  return overlay;
}

function buildWaveBigSvg() {
  const big = document.getElementById("wave_big");
  if (!big) return;
  const c1 = mixHex(currentThemePalette.primary, "#ffffff", 0.55);
  const c2 = mixHex(currentThemePalette.primary, "#ffffff", 0.35);
  const c3 = mixHex(currentThemePalette.primary, "#ffffff", 0.1);
  const c4 = mixHex(currentThemePalette.primary, "#000000", 0.15);
  const c5 = mixHex(currentThemePalette.primary, "#000000", 0.45);
  const stroke = mixHex(currentThemePalette.primary, "#000000", 0.5);
  big.innerHTML = `
    <defs>
      <linearGradient id="mainWaveGrad" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="${c1}"></stop>
        <stop offset="12%" stop-color="${c2}"></stop>
        <stop offset="28%" stop-color="${c3}"></stop>
        <stop offset="56%" stop-color="${c4}"></stop>
        <stop offset="100%" stop-color="${c5}"></stop>
      </linearGradient>
      <linearGradient id="deepWaveGrad" x1="0" x2="1" y1="0" y2="1">
        <stop offset="0%" stop-color="${c4}"></stop>
        <stop offset="100%" stop-color="${c5}"></stop>
      </linearGradient>
    </defs>
    <path d="M760 580 C742 470, 680 392, 610 328 C548 271, 515 221, 504 170 C495 132, 500 98, 535 75 C464 66, 406 84, 366 125 C320 171, 318 231, 350 279 C269 244, 204 253, 162 292 C101 350, 104 444, 174 500 C242 555, 370 590, 760 580 Z" fill="url(#mainWaveGrad)" stroke="${stroke}" stroke-width="3"></path>
    <path d="M600 314 C547 260, 511 210, 500 170 C492 139, 495 110, 512 88" fill="none" stroke="url(#deepWaveGrad)" stroke-width="18" stroke-linecap="round"></path>
    <path d="M566 344 C509 289, 466 234, 446 183 C432 147, 429 120, 437 97" fill="none" stroke="url(#deepWaveGrad)" stroke-width="16" stroke-linecap="round"></path>
  `;
}

function spawnWaveSmall() {
  const layer = document.getElementById("wave_small_layer");
  if (!layer) return;
  const wave = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  wave.setAttribute("viewBox", "0 0 180 120");
  wave.setAttribute("class", "wave-small");
  const y = 20 + Math.random() * (window.innerHeight - 150);
  const dur = 3.8 + Math.random() * 2.3;
  const scale = 0.75 + Math.random() * 0.55;
  const rot = -8 + Math.random() * 16;
  wave.style.top = `${y}px`;
  wave.style.left = `${window.innerWidth + 40 + Math.random() * 160}px`;
  wave.style.animationDuration = `${dur}s`;
  wave.style.transform = `rotate(${rot}deg) scale(${scale})`;
  const gid = `wg${Math.random().toString(36).slice(2)}`;
  const c1 = mixHex(currentThemePalette.primary, "#ffffff", 0.55);
  const c2 = mixHex(currentThemePalette.primary, "#ffffff", 0.28);
  const c3 = mixHex(currentThemePalette.primary, "#000000", 0.18);
  const c4 = mixHex(currentThemePalette.primary, "#000000", 0.45);
  wave.innerHTML = `
    <defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="${c1}"></stop>
      <stop offset="40%" stop-color="${c2}"></stop>
      <stop offset="70%" stop-color="${c3}"></stop>
      <stop offset="100%" stop-color="${c4}"></stop>
    </linearGradient></defs>
    <path d="M165 88 C154 73, 141 62, 126 54 C112 47, 103 40, 100 31 C97 22, 99 15, 107 11 C91 10, 78 15, 70 24 C60 35, 60 46, 68 55 C52 47, 38 49, 29 58 C16 71, 18 90, 34 99 C52 108, 88 108, 165 88 Z" fill="url(#${gid})" stroke="${c4}" stroke-width="2.2"></path>
  `;
  layer.appendChild(wave);
  setTimeout(() => wave.remove(), (dur + 0.5) * 1000);
}

function waveFoamBurst(count = 80) {
  const layer = document.getElementById("wave_foam_layer");
  if (!layer) return;
  const frag = document.createDocumentFragment();
  for (let i = 0; i < count; i++) {
    const dot = document.createElement("div");
    dot.className = "wave-foam";
    const size = 3 + Math.random() * 8;
    const x = window.innerWidth * (0.58 + Math.random() * 0.16);
    const y = window.innerHeight * (0.26 + Math.random() * 0.34);
    const dx = -120 - Math.random() * 260;
    const dy = -120 + Math.random() * 220;
    dot.style.width = `${size}px`;
    dot.style.height = `${size}px`;
    dot.style.left = `${x}px`;
    dot.style.top = `${y}px`;
    dot.style.setProperty("--dx", `${dx}px`);
    dot.style.setProperty("--dy", `${dy}px`);
    frag.appendChild(dot);
    setTimeout(() => dot.remove(), 1300);
  }
  layer.appendChild(frag);
}

function waveStartDrips() {
  const logoLayer = document.getElementById("wave_logo_layer");
  const logoText = document.getElementById("wave_logo_text");
  const dripsLayer = document.getElementById("wave_drips_layer");
  if (!logoLayer || !logoText || !dripsLayer) return;
  logoLayer.classList.add("show");
  logoText.style.color = mixHex(currentThemePalette.primary, "#ffffff", 0.78);
  logoText.style.webkitTextStroke = `2px ${mixHex(currentThemePalette.primary, "#000000", 0.35)}`;
  const create = () => {
    const rect = logoText.getBoundingClientRect();
    const count = 4 + Math.floor(Math.random() * 4);
    for (let i = 0; i < count; i++) {
      const d = document.createElement("div");
      d.className = "wave-drip";
      const x = rect.left + Math.random() * rect.width;
      const y = rect.bottom - 6 + Math.random() * 6;
      const w = 7 + Math.random() * 7;
      const h = w * (1.25 + Math.random() * 0.35);
      const fall = 65 + Math.random() * 130;
      const duration = 1.1 + Math.random() * 1.0;
      d.style.left = `${x}px`;
      d.style.top = `${y}px`;
      d.style.width = `${w}px`;
      d.style.height = `${h}px`;
      d.style.setProperty("--fall", `${fall}px`);
      d.style.animationDuration = `${duration}s`;
      d.style.background = `linear-gradient(180deg, ${mixHex(currentThemePalette.primary, "#ffffff", 0.88)} 0%, ${mixHex(currentThemePalette.primary, "#ffffff", 0.5)} 35%, ${currentThemePalette.primary} 100%)`;
      dripsLayer.appendChild(d);
      setTimeout(() => d.remove(), duration * 1000 + 120);
    }
  };
  create();
  if (waveDripTimer) clearInterval(waveDripTimer);
  waveDripTimer = setInterval(create, 420);
}

function runWaveEffect() {
  if (waveLaunched) return;
  waveLaunched = true;
  ensureWaveOverlay();
  const overlay = document.getElementById("wave_overlay");
  const big = document.getElementById("wave_big");
  const logoLayer = document.getElementById("wave_logo_layer");
  if (!overlay || !big || !logoLayer) return;
  overlay.classList.add("show");
  big.classList.remove("run");
  logoLayer.classList.remove("show");
  buildWaveBigSvg();
  for (let i = 0; i < 14; i++) setTimeout(spawnWaveSmall, i * 130);
  if (waveSpawnerTimer) clearInterval(waveSpawnerTimer);
  waveSpawnerTimer = setInterval(spawnWaveSmall, 190);
  setTimeout(() => {
    big.classList.add("run");
    waveFoamBurst(90);
  }, 2100);
  setTimeout(() => {
    waveStartDrips();
  }, 3600);
  if (waveFinishTimer) clearTimeout(waveFinishTimer);
  waveFinishTimer = setTimeout(() => {
    cleanupWaveEffect();
  }, 7600);
  updateBoomButtons();
}

function cleanupWaveEffect() {
  if (waveFinishTimer) {
    clearTimeout(waveFinishTimer);
    waveFinishTimer = null;
  }
  if (waveSpawnerTimer) {
    clearInterval(waveSpawnerTimer);
    waveSpawnerTimer = null;
  }
  if (waveDripTimer) {
    clearInterval(waveDripTimer);
    waveDripTimer = null;
  }
  if (waveClearTimer) {
    clearTimeout(waveClearTimer);
    waveClearTimer = null;
  }
  waveLaunched = false;
  const overlay = document.getElementById("wave_overlay");
  if (overlay) overlay.classList.remove("show");
  waveClearTimer = setTimeout(() => {
    const small = document.getElementById("wave_small_layer");
    const big = document.getElementById("wave_big");
    const foam = document.getElementById("wave_foam_layer");
    const logo = document.getElementById("wave_logo_layer");
    const drips = document.getElementById("wave_drips_layer");
    if (small) small.innerHTML = "";
    if (big) {
      big.classList.remove("run");
      big.innerHTML = "";
    }
    if (foam) foam.innerHTML = "";
    if (logo) logo.classList.remove("show");
    if (drips) drips.innerHTML = "";
    waveClearTimer = null;
  }, 2300);
  updateBoomButtons();
}

async function api(url, method = "GET", body = null) {
  const options = { method, headers: {} };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || `HTTP ${res.status}`);
  return data;
}

function setValue(id, value) {
  const el = document.getElementById(id);
  if (el && el.value !== undefined) el.value = value ?? "";
}

function escapeHtml(s) {
  return String(s || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function normalizeSpecificFiles(files) {
  if (!Array.isArray(files)) return [];
  return files
    .map((f) => ({
      name: String(f?.name || "").trim(),
      content: String(f?.content || ""),
    }))
    .filter((f) => f.name);
}

function isSpecificModalOpen() {
  const modal = document.getElementById("specific_modal");
  return !!modal && modal.style.display !== "none";
}

function setSpecificFromState(s) {
  specificEnabled = !!s?.specific_enabled;
  specificFiles = normalizeSpecificFiles(s?.specific_files || []);
  if (specificEditorIndex >= specificFiles.length) specificEditorIndex = -1;
  if (specificNameEditingIndex >= specificFiles.length) specificNameEditingIndex = -1;
}

function specificFileTemplate(index, file) {
  const name = String(file?.name || "");
  const editing = specificNameEditingIndex === index;
  const nameHtml = editing
    ? `<input data-specific-act="rename-input" data-idx="${index}" class="specific-file-name-input" type="text" value="${escapeHtml(name)}">`
    : `<button data-specific-act="name" data-idx="${index}" type="button">${escapeHtml(name)}</button>`;
  return `
    <div class="specific-file-row">
      <div>${nameHtml}</div>
      <div class="specific-file-actions">
        <button data-specific-act="view" data-idx="${index}" type="button">👁️</button>
        <button data-specific-act="del" data-idx="${index}" type="button">❌</button>
      </div>
    </div>
  `;
}

async function syncSpecificSettings() {
  await api("/api/settings", "POST", {
    specific_enabled: !!specificEnabled,
    specific_files: specificFiles.map((f) => ({ name: f.name, content: f.content })),
  });
}

function queueSpecificSave() {
  if (specificSaveTimer) clearTimeout(specificSaveTimer);
  specificSaveTimer = setTimeout(async () => {
    try {
      await syncSpecificSettings();
    } catch (e) {
      flash(e.message, false);
    }
  }, 220);
}

function renderSpecificModal() {
  const enabledEl = document.getElementById("specific_enabled");
  const defaultsBtn = document.getElementById("specific_add_defaults_btn");
  const addFileBtn = document.getElementById("specific_add_file_btn");
  const listEl = document.getElementById("specific_files_list");
  const editorWrap = document.getElementById("specific_editor_wrap");
  const editorTitle = document.getElementById("specific_editor_title");
  const editorText = document.getElementById("specific_editor_text");
  if (!enabledEl || !defaultsBtn || !addFileBtn || !listEl || !editorWrap || !editorTitle || !editorText) return;
  enabledEl.checked = !!specificEnabled;
  const showContent = !!specificEnabled;
  defaultsBtn.style.display = showContent ? "" : "none";
  addFileBtn.style.display = showContent ? "" : "none";
  listEl.style.display = showContent ? "" : "none";
  listEl.innerHTML = specificFiles.map((f, idx) => specificFileTemplate(idx, f)).join("");
  const renameInput = listEl.querySelector(`input[data-specific-act="rename-input"][data-idx="${specificNameEditingIndex}"]`);
  if (renameInput instanceof HTMLInputElement) {
    setTimeout(() => {
      renameInput.focus();
      renameInput.select();
    }, 0);
  }
  if (!showContent) {
    editorWrap.style.display = "none";
    editorText.value = "";
    return;
  }
  if (specificEditorIndex >= 0 && specificEditorIndex < specificFiles.length) {
    editorWrap.style.display = "";
    editorTitle.textContent = `${tr("specific_editing_file")}: ${specificFiles[specificEditorIndex].name}`;
    editorText.value = specificFiles[specificEditorIndex].content || "";
  } else {
    editorWrap.style.display = "none";
    editorText.value = "";
  }
}

async function addDefaultSpecificFiles(mode = "add") {
  const d = await api("/api/specific/defaults", "POST", { mode });
  specificFiles = normalizeSpecificFiles(d.files || []);
  renderSpecificModal();
}

async function maybeLoadSpecificFromWorkdirOnEnable() {
  const workdir = document.getElementById("workdir")?.value?.trim() || "";
  if (!workdir) {
    if (!specificFiles.length) await addDefaultSpecificFiles("replace");
    return;
  }
  let info = null;
  try {
    info = await api("/api/specific/workdir-files", "POST", { workdir });
  } catch (_e) {
    if (!specificFiles.length) await addDefaultSpecificFiles("replace");
    return;
  }
  if (!info?.exists) {
    if (!specificFiles.length) await addDefaultSpecificFiles("replace");
    return;
  }
  if (specificFiles.length) {
    if (confirm(tr("specific_confirm_add_from_workdir"))) {
      const d = await api("/api/specific/load-from-workdir", "POST", { workdir, mode: "add" });
      specificFiles = normalizeSpecificFiles(d.files || []);
    }
  } else {
    if (confirm(tr("specific_confirm_replace_from_workdir"))) {
      const d = await api("/api/specific/load-from-workdir", "POST", { workdir, mode: "replace" });
      specificFiles = normalizeSpecificFiles(d.files || []);
    } else {
      await addDefaultSpecificFiles("replace");
    }
  }
}

function initializeModeAdvancedDefaults() {
  for (const mode of MODES) {
    const merged = {};
    for (const key of ADV_KEYS) {
      merged[key] = modeCache[mode].advanced_params[key] ?? ADV_DEFAULTS[key] ?? "";
    }
    modeCache[mode].advanced_params = merged;
  }
}

function renderAdvancedFields() {
  const block = document.getElementById("advanced_block");
  if (!block) return;
  const groupsHtml = ADV_GROUPS.map((group, idx) => {
    const isOpen = advGroupOpenByIndex[idx] !== false;
    const fieldsHtml = group.fields.map((field) => {
      const control = ADV_MULTILINE_KEYS.has(field.key)
        ? `<textarea id="adv_${field.key}" class="adv-multiline-input" rows="1"></textarea>`
        : `<input id="adv_${field.key}" type="text">`;
      return `
      <label class="adv-param" for="adv_${field.key}">
        <span class="adv-param-title">
          <span class="adv-param-key has-tip" tabindex="0" data-adv-tip="${escapeHtml(field.key)}" aria-label="${escapeHtml(tr("adv_help_aria"))}">
            ${escapeHtml(field.key)}
            <span class="help-tooltip" data-adv-tip="${escapeHtml(field.key)}">${escapeHtml(advTipText(field))}</span>
          </span>
        </span>
        ${control}
      </label>
    `;
    }).join("");
    return `
      <section class="adv-group">
        <div class="adv-group-head">
          <h4 class="adv-group-title" data-adv-group="${idx}">${escapeHtml(advGroupTitle(idx, group.title))}</h4>
          <button type="button" class="adv-group-toggle" data-act="adv-group-toggle" data-idx="${idx}" aria-expanded="${isOpen ? "true" : "false"}">${isOpen ? "▾" : "▸"}</button>
        </div>
        <div id="adv_group_content_${idx}" class="adv-group-content${isOpen ? " open" : ""}">
          <div class="adv-group-fields">${fieldsHtml}</div>
        </div>
      </section>
    `;
  }).join("");
  block.innerHTML = groupsHtml;
}

function autoSizeAdvTextarea(el) {
  if (!(el instanceof HTMLTextAreaElement)) return;
  el.style.height = "auto";
  const h = Math.max(34, Math.min(el.scrollHeight, 320));
  el.style.height = `${h}px`;
}

function collapseAdvTextarea(el) {
  if (!(el instanceof HTMLTextAreaElement)) return;
  el.classList.add("is-collapsed");
  el.style.height = "";
}

function expandAdvTextarea(el) {
  if (!(el instanceof HTMLTextAreaElement)) return;
  el.classList.remove("is-collapsed");
  autoSizeAdvTextarea(el);
}

function bindAdvancedMultilineEditors() {
  for (const key of ADV_MULTILINE_KEYS) {
    const el = document.getElementById(`adv_${key}`);
    if (!(el instanceof HTMLTextAreaElement)) continue;
    collapseAdvTextarea(el);
    el.addEventListener("focus", () => expandAdvTextarea(el));
    el.addEventListener("input", () => autoSizeAdvTextarea(el));
    el.addEventListener("blur", () => collapseAdvTextarea(el));
  }
}

function restoreAdvancedMultilineCollapsedState() {
  for (const key of ADV_MULTILINE_KEYS) {
    const el = document.getElementById(`adv_${key}`);
    if (!(el instanceof HTMLTextAreaElement)) continue;
    if (document.activeElement !== el) collapseAdvTextarea(el);
  }
}

function formatValue(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "-";
  return String(v);
}

function formatSeedCheckInfo(info) {
  const count = info?.count ?? 0;
  const elements = Array.isArray(info?.elements) ? info.elements.join(", ") : "";
  const systems = Array.isArray(info?.systems) ? info.systems.join("\n") : "";
  return `number of structures ${count}\n` +
    `elements ${elements}\n` +
    `systems\n${systems}`;
}

function displayGeneration(structure, groupGeneration) {
  const manual = !!structure?.generation_user_set;
  if (manual) return structure?.seed_generation ?? "";
  return groupGeneration ?? "";
}

function applyGroupGenerationLocally(groupId, generationValue) {
  const gid = Number(groupId);
  const group = (appState?.seed_groups || []).find((g) => Number(g.id) === gid);
  if (!group) return;
  const value = String(generationValue ?? "");
  group.group_generation = value ? value : null;
  (group.structures || []).forEach((s, idx) => {
    if (!s.generation_user_set) {
      s.seed_generation = value ? value : null;
      const input = document.querySelector(
        `input[data-act="seed-struct-generation"][data-id="${gid}"][data-idx="${idx}"]`
      );
      if (input) input.value = value;
    }
  });
}
function applyAntiGroupGenerationLocally(groupId, generationValue) {
  const gid = Number(groupId);
  const group = (appState?.anti_seed_groups || []).find((g) => Number(g.id) === gid);
  if (!group) return;
  const value = String(generationValue ?? "");
  group.group_generation = value ? value : null;
  (group.structures || []).forEach((s, idx) => {
    if (!s.generation_user_set) {
      s.seed_generation = value ? value : null;
      const input = document.querySelector(
        `input[data-act="anti-seed-struct-generation"][data-id="${gid}"][data-idx="${idx}"]`
      );
      if (input) input.value = value;
    }
  });
}

function currentMode() {
  return document.getElementById("mode").value || "fixed";
}

function markModeButtons(mode) {
  MODES.forEach((m) => {
    const btn = document.getElementById(`mode_${m}_btn`);
    if (btn) btn.classList.toggle("active", mode === m);
  });
}

function readCurrentFormIntoModeCache() {
  const mode = currentMode();
  modeCache[mode].elements_text = document.getElementById("elements_text").value;
  modeCache[mode].counts_text = document.getElementById("counts_text").value;
  modeCache[mode].ratios_text = document.getElementById("ratios_text").value;
  modeCache[mode].min_at_text = document.getElementById("min_at_text").value;
  modeCache[mode].max_at_text = document.getElementById("max_at_text").value;
  modeCache[mode].advanced_enabled = document.getElementById("adv_toggle").checked;
  for (const k of ADV_KEYS) {
    modeCache[mode].advanced_params[k] = document.getElementById(`adv_${k}`).value;
  }
  modeCache[mode].preview_text = document.getElementById("preview_text").value;
  modeCache[mode].preview_dirty = modeCache[mode].preview_text !== expectedPreviewText;
}

function writeModeCacheToForm(mode) {
  const c = modeCache[mode];
  setValue("elements_text", c.elements_text);
  setValue("counts_text", c.counts_text);
  setValue("ratios_text", c.ratios_text);
  setValue("min_at_text", c.min_at_text);
  setValue("max_at_text", c.max_at_text);
  for (const k of ADV_KEYS) {
    setValue(`adv_${k}`, c.advanced_params[k] || "");
  }
  restoreAdvancedMultilineCollapsedState();
  const advCb = document.getElementById("adv_toggle");
  if (advCb) advCb.checked = !!modeCache[mode].advanced_enabled;
  document.getElementById("preview_text").value = modeCache[mode].preview_text || "";
}

function modeStateFromCache() {
  const out = {};
  for (const m of MODES) {
    out[m] = {
      elements_text: modeCache[m].elements_text,
      counts_text: modeCache[m].counts_text,
      ratios_text: modeCache[m].ratios_text,
      min_at_text: modeCache[m].min_at_text,
      max_at_text: modeCache[m].max_at_text,
      advanced_enabled: !!modeCache[m].advanced_enabled,
      advanced_params: { ...modeCache[m].advanced_params },
      preview_text: modeCache[m].preview_text || "",
      preview_dirty: !!modeCache[m].preview_dirty,
    };
  }
  return out;
}

function updateModeVisibility() {
  const mode = currentMode();
  document.getElementById("field_counts").style.display = mode === "fixed" ? "" : "none";
  document.getElementById("field_ratios").style.display = mode === "single" ? "" : "none";
  document.getElementById("field_min_at").style.display = mode === "single" || mode === "variable" ? "" : "none";
  document.getElementById("field_max_at").style.display = mode === "single" || mode === "variable" ? "" : "none";
  document.getElementById("advanced_block").style.display = modeCache[mode].advanced_enabled ? "" : "none";
  const advCb = document.getElementById("adv_toggle");
  if (advCb) advCb.checked = !!modeCache[mode].advanced_enabled;
}

function updateSeedsVisibility() {
  const enabled = document.getElementById("seeds_enabled").checked;
  document.getElementById("seeds_content").style.display = enabled ? "" : "none";
}
function updateAntiSeedsVisibility() {
  const enabled = document.getElementById("anti_seeds_enabled").checked;
  document.getElementById("anti_seeds_content").style.display = enabled ? "" : "none";
}

function updatePreviewDirtyUI() {
  const previewEl = document.getElementById("preview_text");
  const resetBtn = document.getElementById("preview_reset_btn");
  const hint = document.getElementById("preview_dirty_hint");
  const dirty = previewEl.value !== expectedPreviewText;
  resetBtn.style.display = dirty ? "" : "none";
  hint.style.display = dirty ? "" : "none";
}

function switchMode(target) {
  readCurrentFormIntoModeCache();
  document.getElementById("mode").value = target;
  markModeButtons(target);
  writeModeCacheToForm(target);
  updateModeVisibility();
  updatePreviewDirtyUI();
}

function renderSeeds(groups) {
  const root = document.getElementById("seed_groups");
  root.innerHTML = "";
  const structuresText = tr("structures_word") || "structures";
  const elementsText = tr("elements_word") || "elements";
  const addToGenerationText = tr("add_to_generation");
  const resetGenerationsText = tr("reset_generations");
  const structureLabel = tr("structure_label");
  const copyStructureText = tr("copy_structure_title");
  groups.forEach((g) => {
    if (seedGroupOpenById[g.id] === undefined) {
      seedGroupOpenById[g.id] = true;
    }
    const isGroupOpen = !!seedGroupOpenById[g.id];
    const wrap = document.createElement("div");
    wrap.className = "seed-group";
    const stats = g.stats || {};
    const elems = Array.isArray(stats.elements) ? stats.elements.join(" ") : "";
    const count = stats.count || 0;
    const prefix = g.source_label ? `${g.source_label} | ` : "";
    const groupGeneration = g.group_generation ?? "";
    wrap.innerHTML = `
      <div class="seed-head">
        <div class="seed-head-main">
          <button data-act="seed-toggle-group" data-id="${g.id}" class="seed-group-toggle">${isGroupOpen ? "▾" : "▸"}</button>
          <div><b>${prefix}${count} ${structuresText} ${elementsText} ${elems}</b><div>${escapeHtml(g.path || "")}</div></div>
        </div>
        <div class="seed-head-actions">
          <label class="seed-gen-label-inline">${escapeHtml(addToGenerationText)}</label>
          <input data-act="seed-group-generation" data-id="${g.id}" class="seed-gen-inline" type="text" inputmode="numeric" pattern="[0-9]*" value="${escapeHtml(groupGeneration)}">
          <button data-act="seed-reset-group-generations" data-id="${g.id}" title="${escapeHtml(resetGenerationsText)}">↻</button>
          <button data-act="seed-viz-group" data-id="${g.id}">🖼️</button>
          <button class="danger" data-act="seed-del-group" data-id="${g.id}">❌</button>
        </div>
      </div>
      <div id="seed_group_${g.id}" class="seed-group-content${isGroupOpen ? " open" : ""}"></div>
    `;
    const groupContent = wrap.querySelector(`#seed_group_${g.id}`);
    (g.structures || []).forEach((s, idx) => {
      const key = `${g.id}_${idx}`;
      const isOpen = !!seedTextOpenByKey[key];
      const structGeneration = displayGeneration(s, g.group_generation);
      const row = document.createElement("div");
      row.className = "seed-structure";
      row.innerHTML = `
        <div>
          #${s.index ?? idx + 1} | ${escapeHtml(s.formula || "")} | Gen=${escapeHtml(formatValue(s.Gen))} | generation=${escapeHtml(formatValue(s.generation))} | number=${escapeHtml(formatValue(s.number))} | energy=${escapeHtml(formatValue(s.energy))}
          <div class="seed-details">
            <div class="row">
              <button data-act="seed-toggle-struct" data-key="${key}" class="seed-toggle">${isOpen ? "▾" : "▸"} ${escapeHtml(structureLabel)}</button>
            </div>
            <div id="seed_text_${key}" class="seed-text-wrap${isOpen ? " open" : ""}">
              <div class="seed-text-toolbar">
                <button data-act="seed-copy-struct" data-id="${g.id}" data-idx="${idx}" title="${escapeHtml(copyStructureText)}">📋</button>
              </div>
              <pre class="mono-block">${escapeHtml(s.structure || "")}</pre>
            </div>
          </div>
        </div>
        <input data-act="seed-struct-generation" data-id="${g.id}" data-idx="${idx}" class="seed-gen-inline seed-gen-struct" type="text" inputmode="numeric" pattern="[0-9]*" value="${escapeHtml(structGeneration)}">
        <button data-act="seed-viz-struct" data-id="${g.id}" data-idx="${idx}">🖼️</button>
        <button class="danger" data-act="seed-del-struct" data-id="${g.id}" data-idx="${idx}">❌</button>
      `;
      groupContent.appendChild(row);
    });
    root.appendChild(wrap);
  });
}

function renderAntiSeeds(groups) {
  const root = document.getElementById("anti_seed_groups");
  root.innerHTML = "";
  const structuresText = tr("structures_word") || "structures";
  const elementsText = tr("elements_word") || "elements";
  const addToGenerationText = tr("add_to_generation");
  const resetGenerationsText = tr("reset_generations");
  const structureLabel = tr("structure_label");
  const copyStructureText = tr("copy_structure_title");
  groups.forEach((g) => {
    if (antiSeedGroupOpenById[g.id] === undefined) {
      antiSeedGroupOpenById[g.id] = true;
    }
    const isGroupOpen = !!antiSeedGroupOpenById[g.id];
    const wrap = document.createElement("div");
    wrap.className = "seed-group";
    const stats = g.stats || {};
    const elems = Array.isArray(stats.elements) ? stats.elements.join(" ") : "";
    const count = stats.count || 0;
    const prefix = g.source_label ? `${g.source_label} | ` : "";
    const groupGeneration = g.group_generation ?? "";
    wrap.innerHTML = `
      <div class="seed-head">
        <div class="seed-head-main">
          <button data-act="anti-seed-toggle-group" data-id="${g.id}" class="seed-group-toggle">${isGroupOpen ? "▾" : "▸"}</button>
          <div><b>${prefix}${count} ${structuresText} ${elementsText} ${elems}</b><div>${escapeHtml(g.path || "")}</div></div>
        </div>
        <div class="seed-head-actions">
          <label class="seed-gen-label-inline">${escapeHtml(addToGenerationText)}</label>
          <input data-act="anti-seed-group-generation" data-id="${g.id}" class="seed-gen-inline" type="text" inputmode="numeric" pattern="[0-9]*" value="${escapeHtml(groupGeneration)}">
          <button data-act="anti-seed-reset-group-generations" data-id="${g.id}" title="${escapeHtml(resetGenerationsText)}">↻</button>
          <button data-act="anti-seed-viz-group" data-id="${g.id}">🖼️</button>
          <button class="danger" data-act="anti-seed-del-group" data-id="${g.id}">❌</button>
        </div>
      </div>
      <div id="anti_seed_group_${g.id}" class="seed-group-content${isGroupOpen ? " open" : ""}"></div>
    `;
    const groupContent = wrap.querySelector(`#anti_seed_group_${g.id}`);
    (g.structures || []).forEach((s, idx) => {
      const key = `${g.id}_${idx}`;
      const isOpen = !!antiSeedTextOpenByKey[key];
      const structGeneration = displayGeneration(s, g.group_generation);
      const row = document.createElement("div");
      row.className = "seed-structure";
      row.innerHTML = `
        <div>
          #${s.index ?? idx + 1} | ${escapeHtml(s.formula || "")} | Gen=${escapeHtml(formatValue(s.Gen))} | generation=${escapeHtml(formatValue(s.generation))} | number=${escapeHtml(formatValue(s.number))} | energy=${escapeHtml(formatValue(s.energy))}
          <div class="seed-details">
            <div class="row">
              <button data-act="anti-seed-toggle-struct" data-key="${key}" class="seed-toggle">${isOpen ? "▾" : "▸"} ${escapeHtml(structureLabel)}</button>
            </div>
            <div id="anti_seed_text_${key}" class="seed-text-wrap${isOpen ? " open" : ""}">
              <div class="seed-text-toolbar">
                <button data-act="anti-seed-copy-struct" data-id="${g.id}" data-idx="${idx}" title="${escapeHtml(copyStructureText)}">📋</button>
              </div>
              <pre class="mono-block">${escapeHtml(s.structure || "")}</pre>
            </div>
          </div>
        </div>
        <input data-act="anti-seed-struct-generation" data-id="${g.id}" data-idx="${idx}" class="seed-gen-inline seed-gen-struct" type="text" inputmode="numeric" pattern="[0-9]*" value="${escapeHtml(structGeneration)}">
        <button data-act="anti-seed-viz-struct" data-id="${g.id}" data-idx="${idx}">🖼️</button>
        <button class="danger" data-act="anti-seed-del-struct" data-id="${g.id}" data-idx="${idx}">❌</button>
      `;
      groupContent.appendChild(row);
    });
    root.appendChild(wrap);
  });
}

async function renderPreviewResults(previewData) {
  const root = document.getElementById("preview_results");
  root.innerHTML = "";
  const structures = previewData?.structures || {};
  const entries = Object.entries(structures);
  if (!entries.length) {
    root.textContent = tr("no_results");
    root.style.maxHeight = "";
    root.style.overflowY = "";
    return;
  }
  for (const [n, stagesObj] of entries) {
    const row = document.createElement("div");
    row.className = "preview-line";
    const stages = [1, 2, 3].map((stage) => ({ stage, info: stagesObj[String(stage)] || stagesObj[stage] }));
    const buttons = stages
      .map(({ stage, info }) => {
        if (!info?.has_output) return `<span>— ${escapeHtml(tr("stage_label").toLowerCase())} ${stage}</span>`;
        return `<button data-act="preview-toggle" data-n="${n}" data-stage="${stage}" data-path="${info.output_xyz}">✅ ${stage}</button>`;
      })
      .join(" ");
    row.innerHTML = `<b>N=${n}</b><div class="preview-actions">${buttons}</div><div id="preview_target_${n}" class="preview-target"></div>`;
    root.appendChild(row);
    const opened = openPreviewByN[n];
    if (opened?.path) {
      const target = document.getElementById(`preview_target_${n}`);
      try {
        const d = await api("/api/preview/read-output", "POST", { path: opened.path });
        target.innerHTML = `
          <div class="row">
            <button data-act="preview-viz" data-path="${opened.path}">🖼️</button>
            <span>${escapeHtml(tr("stage_label"))} ${opened.stage}</span>
            <span>${escapeHtml(opened.path)}</span>
          </div>
          <pre>${escapeHtml(d.content || "")}</pre>
        `;
      } catch (e) {
        target.innerHTML = `<div class="mono-card">${escapeHtml(e.message)}</div>`;
      }
    }
  }
  updatePreviewResultsViewport();
}

function updatePreviewResultsViewport() {
  const root = document.getElementById("preview_results");
  if (!root) return;
  const rows = Array.from(root.querySelectorAll(".preview-line"));
  const limit = 5;
  if (rows.length <= limit) {
    root.style.maxHeight = "";
    root.style.overflowY = "";
    return;
  }
  const first = rows[0];
  const next = rows[limit];
  const last = rows[limit - 1];
  const lastStyle = getComputedStyle(last);
  const lastMarginBottom = parseFloat(lastStyle.marginBottom || "0") || 0;
  const rootStyle = getComputedStyle(root);
  const rootPadTop = parseFloat(rootStyle.paddingTop || "0") || 0;
  const rootPadBottom = parseFloat(rootStyle.paddingBottom || "0") || 0;
  const cutoff = next
    ? next.offsetTop
    : (last.offsetTop + last.offsetHeight + lastMarginBottom);
  const total = cutoff - first.offsetTop + rootPadTop + rootPadBottom;
  root.style.maxHeight = `${Math.max(Math.ceil(total + 18), 320)}px`;
  root.style.overflowY = "auto";
}

function renderBrowserList(data) {
  browserListingData = {
    dirs: Array.isArray(data?.dirs) ? data.dirs : [],
    files: Array.isArray(data?.files) ? data.files : [],
  };
  const dirs = document.getElementById("browser_dirs");
  const files = document.getElementById("browser_files");
  dirs.innerHTML = "";
  files.innerHTML = "";
  for (const d of browserListingData.dirs) {
    const row = document.createElement("div");
    row.className = "browser-item";
    row.dataset.path = d.path;
    row.innerHTML = `<span class="name">📁 ${escapeHtml(d.name)}</span><button data-act="browser-enter" data-path="${d.path}">${escapeHtml(tr("open_file"))}</button>`;
    dirs.appendChild(row);
  }
  const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".tiff", ".tif"]);
  for (const f of browserListingData.files) {
    const isOpen = !!browserFileOpenByPath[f.path];
    const text = browserFileContentByPath[f.path] ?? "";
    const name = String(f.name || "");
    const lower = name.toLowerCase();
    const isImage = IMAGE_EXTS.has(lower.slice(lower.lastIndexOf(".")));
    const hideActions = lower.endsWith(".exe") || lower.endsWith(".pdf");
    const row = document.createElement("div");
    row.className = "browser-file-item";
    const actions = hideActions
      ? ""
      : `
        <button data-act="browser-read" data-path="${f.path}">${escapeHtml(isOpen ? tr("hide_file") : tr("open_file"))}</button>
        ${isImage ? "" : `<button data-act="browser-viz" data-path="${f.path}">${escapeHtml(tr("view_btn"))}</button>`}
        <button data-act="browser-seed-check" data-path="${f.path}">${escapeHtml(tr("check_btn"))}</button>
        <button data-act="browser-seed-add" data-path="${f.path}">${escapeHtml(tr("to_seeds_btn"))}</button>
        <button data-act="browser-anti-seed-add" data-path="${f.path}">${escapeHtml(tr("to_antiseeds_btn"))}</button>
      `;
    const previewContent = isImage
      ? `<img src="/api/browser/file?path=${encodeURIComponent(f.path)}" alt="${escapeHtml(name)}" style="max-width:100%;display:block;">`
      : `<pre class="mono-block">${escapeHtml(text)}</pre>`;
    const preview = hideActions
      ? ""
      : `
      <div class="browser-inline-preview${isOpen ? " open" : ""}">
        ${isImage ? "" : `<div class="browser-preview-toolbar"><button data-act="browser-copy" data-path="${f.path}" title="${escapeHtml(tr("copy_file_title"))}">📋</button></div>`}
        ${previewContent}
      </div>
      `;
    row.innerHTML = `
      <div class="browser-item">
        <span class="name">${isImage ? "🖼️" : "📄"} ${escapeHtml(f.name)}</span>
        ${actions}
      </div>
      ${preview}
    `;
    files.appendChild(row);
  }
}

function shouldRestorePageScroll(refreshStartAt) {
  return lastUserScrollAt <= refreshStartAt;
}

function rememberBrowserPanelSize() {
  const panel = document.getElementById("file_browser_panel");
  if (!panel || browserPanelSizeSnapshot.active) return;
  browserPanelSizeSnapshot.active = true;
  browserPanelSizeSnapshot.width = panel.style.width || "";
  browserPanelSizeSnapshot.maxWidth = panel.style.maxWidth || "";
  browserPanelSizeSnapshot.minHeight = panel.style.minHeight || "";
  browserPanelSizeSnapshot.pxWidth = panel.offsetWidth || 0;
  if (browserPanelSizeSnapshot.pxWidth > 0) {
    panel.style.width = `${browserPanelSizeSnapshot.pxWidth}px`;
    panel.style.maxWidth = `${browserPanelSizeSnapshot.pxWidth}px`;
  }
}

function restoreBrowserPanelSizeIfNoOpenPreviews() {
  const panel = document.getElementById("file_browser_panel");
  if (!panel || !browserPanelSizeSnapshot.active) return;
  const hasOpen = Object.values(browserFileOpenByPath).some(Boolean);
  if (hasOpen) return;
  panel.style.width = browserPanelSizeSnapshot.width;
  panel.style.maxWidth = browserPanelSizeSnapshot.maxWidth;
  panel.style.minHeight = browserPanelSizeSnapshot.minHeight;
  browserPanelSizeSnapshot.active = false;
}

async function refreshState(hydrateForms = false, preservePageScroll = false) {
  if (refreshInFlight) return;
  refreshInFlight = true;
  const refreshStartAt = performance.now();
  const pageYBefore = preservePageScroll ? window.scrollY : 0;
  try {
    const s = await api("/api/state");
    appState = s;
    if (!isSpecificModalOpen() || hydrateForms || !formHydrated) {
      setSpecificFromState(s);
    }
    expectedPreviewText = s.expected_preview || s.preview_text || "";
    if (hydrateForms || !formHydrated) {
      setValue("exe_path", s.exe_path);
      setValue("stmng_exe_path", s.stmng_path || "");
      setValue("workdir", s.workdir);
      setValue("mode", s.mode);
      setValue("mp_api_key", s.materials_project_api_key || "");
      setValue("mp_chemsys", s.mp_chemsys);
      setValue("mp_ehull_max", s.mp_ehull_max);
      setValue("anti_mp_api_key", s.anti_materials_project_api_key || "");
      setValue("anti_mp_chemsys", s.anti_mp_chemsys);
      setValue("anti_mp_ehull_max", s.anti_mp_ehull_max);
      document.getElementById("seeds_enabled").checked = !!s.seeds_enabled;
      document.getElementById("anti_seeds_enabled").checked = !!s.anti_seeds_enabled;
      document.getElementById("preview_text").value = s.preview_text || "";
    }
    const stmngEl = document.getElementById("stmng_status");
    if (stmngEl) {
      if (s.stmng_installed) {
        stmngEl.textContent = `${tr("stmng_installed")} (${s.stmng_path || ""})`;
        stmngEl.style.color = "#126b2e";
      } else {
        stmngEl.textContent = `${tr("stmng_missing")} ${s.stmng_path || ""}. ${tr("stmng_install_hint")}`;
        stmngEl.style.color = "#9b1d37";
      }
    }
    updateSeedsVisibility();
    updateAntiSeedsVisibility();

    const mode = s.mode || "fixed";
    if (s.mode_state && typeof s.mode_state === "object") {
      for (const m of MODES) {
        const src = s.mode_state[m];
        if (!src) continue;
        modeCache[m].elements_text = src.elements_text ?? modeCache[m].elements_text;
        modeCache[m].counts_text = src.counts_text ?? modeCache[m].counts_text;
        modeCache[m].ratios_text = src.ratios_text ?? modeCache[m].ratios_text;
        modeCache[m].min_at_text = src.min_at_text ?? modeCache[m].min_at_text;
        modeCache[m].max_at_text = src.max_at_text ?? modeCache[m].max_at_text;
        modeCache[m].advanced_enabled = !!src.advanced_enabled;
        if (src.advanced_params && typeof src.advanced_params === "object") {
          modeCache[m].advanced_params = { ...modeCache[m].advanced_params, ...src.advanced_params };
        }
        modeCache[m].preview_text = src.preview_text ?? modeCache[m].preview_text;
        modeCache[m].preview_dirty = !!src.preview_dirty;
      }
    }

    if (hydrateForms || !formHydrated) {
      markModeButtons(mode);
      writeModeCacheToForm(mode);
      updateModeVisibility();
      if (!modeCache[mode].preview_text) {
        document.getElementById("preview_text").value = s.preview_text || "";
      }
    }
    updatePreviewDirtyUI();
    formHydrated = true;

    document.getElementById("status_line").textContent =
      `${tr("status_prefix")}: stage=${s.status?.stage || "idle"} | gen=${s.status?.generation ?? "-"} | done=${s.status?.done_steps ?? 0} | total=${s.status?.total_steps ?? 0} | gen_size=${s.status?.gen_size ?? "-"}`;
    const seedGroups = s.seed_groups || [];
    const seedGroupsSignature = JSON.stringify(seedGroups);
    if (!seedGenerationEditing && seedGroupsSignature !== lastSeedGroupsSignature) {
      renderSeeds(seedGroups);
      lastSeedGroupsSignature = seedGroupsSignature;
    }
    const antiSeedGroups = s.anti_seed_groups || [];
    const antiSeedGroupsSignature = JSON.stringify(antiSeedGroups);
    if (!antiSeedGenerationEditing && antiSeedGroupsSignature !== lastAntiSeedGroupsSignature) {
      renderAntiSeeds(antiSeedGroups);
      lastAntiSeedGroupsSignature = antiSeedGroupsSignature;
    }
    const previewRoot = document.getElementById("preview_results");
    const previewScrollTopBefore = previewRoot ? previewRoot.scrollTop : 0;
    const previewAtBottomBefore = previewRoot
      ? Math.abs((previewRoot.scrollHeight - previewRoot.clientHeight) - previewRoot.scrollTop) < 4
      : false;
    const structuresSignature = JSON.stringify(s.preview_results?.structures || {});
    const shouldRenderPreview = !preservePageScroll || structuresSignature !== lastPreviewStructuresSignature;
    if (shouldRenderPreview) {
      await renderPreviewResults(s.preview_results || {});
      lastPreviewStructuresSignature = structuresSignature;
      const previewRootAfter = document.getElementById("preview_results");
      if (previewRootAfter) {
        if (previewAtBottomBefore) {
          previewRootAfter.scrollTop = previewRootAfter.scrollHeight;
        } else {
          previewRootAfter.scrollTop = previewScrollTopBefore;
        }
      }
    }
    if (!browserState.root) {
      const initPath = s.browser_current_path || s.workdir || "";
      setValue("browser_current", initPath);
      loadBrowser(initPath).catch(() => {});
    }
    if (preservePageScroll && shouldRestorePageScroll(refreshStartAt) && window.scrollY !== pageYBefore) {
      window.scrollTo(0, pageYBefore);
    }
  } catch (e) {
    flash(e.message, false);
  } finally {
    refreshInFlight = false;
  }
}

async function pollLog() {
  if (pollLogInFlight) return;
  pollLogInFlight = true;
  const pollStartAt = performance.now();
  try {
    const d = await api(`/api/log?since=${logVersion}`);
    logVersion = d.version;
    if (d.lines && d.lines.length) {
      const logEl = document.getElementById("log_text");
      const nextText = d.lines.join("\n");
      if (!logEl || logEl.value === nextText) return;

      const active = document.activeElement;
      const wasFocused = active === logEl;
      const pageY = window.scrollY;
      const atBottom =
        Math.abs((logEl.scrollHeight - logEl.clientHeight) - logEl.scrollTop) < 4;
      if (wasFocused) {
        logEl.blur();
      }

      logEl.value = nextText;

      if (atBottom) {
        logEl.scrollTop = logEl.scrollHeight;
      }
      if (shouldRestorePageScroll(pollStartAt) && window.scrollY !== pageY) window.scrollTo(0, pageY);
    }
  } catch (_e) {
  } finally {
    pollLogInFlight = false;
  }
}

async function saveSettings(includePreviewText = true, forcePreviewFromParams = false) {
  readCurrentFormIntoModeCache();
  const mode = currentMode();
  const c = modeCache[mode];
  const advancedParams = {};
  for (const k of ADV_KEYS) advancedParams[k] = c.advanced_params[k] || "";
  const payload = {
    exe_path: document.getElementById("exe_path").value,
    stmng_path: document.getElementById("stmng_exe_path").value,
    workdir: document.getElementById("workdir").value,
    mode,
    elements_text: c.elements_text,
    counts_text: c.counts_text,
    ratios_text: c.ratios_text,
    min_at_text: c.min_at_text,
    max_at_text: c.max_at_text,
    advanced_enabled: c.advanced_enabled,
    advanced_params: advancedParams,
    mode_state: modeStateFromCache(),
    preview_text: document.getElementById("preview_text").value,
    mp_chemsys: document.getElementById("mp_chemsys").value,
    mp_ehull_max: document.getElementById("mp_ehull_max").value,
    materials_project_api_key: document.getElementById("mp_api_key").value,
    anti_mp_chemsys: document.getElementById("anti_mp_chemsys").value,
    anti_mp_ehull_max: document.getElementById("anti_mp_ehull_max").value,
    anti_materials_project_api_key: document.getElementById("anti_mp_api_key").value,
    seeds_enabled: document.getElementById("seeds_enabled").checked,
    anti_seeds_enabled: document.getElementById("anti_seeds_enabled").checked,
    specific_enabled: !!specificEnabled,
    specific_files: specificFiles.map((f) => ({ name: f.name, content: f.content })),
  };
  if (includePreviewText) {
    payload.preview_text = document.getElementById("preview_text").value;
  }
  if (forcePreviewFromParams) {
    payload.force_preview_from_params = true;
  }
  await api("/api/settings", "POST", payload);
}

function queuePathAutoSave() {
  if (pathSaveTimer) clearTimeout(pathSaveTimer);
  pathSaveTimer = setTimeout(async () => {
    try {
      await api("/api/settings", "POST", {
        exe_path: document.getElementById("exe_path").value,
        stmng_path: document.getElementById("stmng_exe_path").value,
        workdir: document.getElementById("workdir").value,
      });
    } catch (e) {
      flash(e.message, false);
    }
  }, 250);
}

function queueMpAutoSave() {
  if (mpSaveTimer) clearTimeout(mpSaveTimer);
  mpSaveTimer = setTimeout(async () => {
    try {
      await saveMpSettingsNow();
    } catch (e) {
      flash(e.message, false);
    }
  }, 250);
}

async function saveMpSettingsNow() {
  await api("/api/settings", "POST", {
    materials_project_api_key: document.getElementById("mp_api_key").value,
    mp_chemsys: document.getElementById("mp_chemsys").value,
    mp_ehull_max: document.getElementById("mp_ehull_max").value,
    anti_materials_project_api_key: document.getElementById("anti_mp_api_key").value,
    anti_mp_chemsys: document.getElementById("anti_mp_chemsys").value,
    anti_mp_ehull_max: document.getElementById("anti_mp_ehull_max").value,
  });
}

function queuePreviewSync() {
  if (previewSyncTimer) clearTimeout(previewSyncTimer);
  previewSyncTimer = setTimeout(async () => {
    try {
      const m = currentMode();
      const dirty = !!modeCache[m].preview_dirty;
      if (dirty) {
        await saveSettings(true, false);
      } else {
        await saveSettings(false, true);
      }
      const s = await api("/api/state");
      expectedPreviewText = s.expected_preview || s.preview_text || "";
      if (!dirty) {
        document.getElementById("preview_text").value = s.preview_text || "";
      }
      const modeNow = currentMode();
      modeCache[modeNow].preview_text = s.preview_text || "";
      modeCache[modeNow].preview_dirty = !!s.preview_dirty;
      updatePreviewDirtyUI();
    } catch (e) {
      flash(e.message, false);
    }
  }, 220);
}

function browserRoot() {
  return document.getElementById("workdir").value.trim();
}

async function loadBrowser(pathOverride = null) {
  const root = browserRoot();
  let current = pathOverride ?? document.getElementById("browser_current").value.trim();
  if (!current) current = root;
  const d = await api("/api/browser/list", "POST", { root, current });
  browserState = { root: d.root, current: d.current, parent: d.parent, canGoUp: d.can_go_up };
  setValue("browser_current", d.current);
  renderBrowserList(d);
  api("/api/settings", "POST", { browser_current_path: d.current }).catch(() => {});
}

function browserOpenTyped() {
  const typed = document.getElementById("browser_current").value.trim();
  loadBrowser(typed || browserRoot()).catch((e) => flash(e.message, false));
}

document.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  const act = btn.dataset.act;
  if (!act) return;
  if (act === "adv-group-toggle") {
    const idx = Number(btn.dataset.idx);
    const nextOpen = !(advGroupOpenByIndex[idx] !== false);
    advGroupOpenByIndex[idx] = nextOpen;
    saveAdvGroupOpenState();
    const panel = document.getElementById(`adv_group_content_${idx}`);
    if (panel) panel.classList.toggle("open", nextOpen);
    btn.textContent = nextOpen ? "▾" : "▸";
    btn.setAttribute("aria-expanded", nextOpen ? "true" : "false");
    return;
  }
  let actionMessage = "";
  try {
    if (act === "seed-del-group") {
      await api("/api/seeds/delete-group", "POST", { group_id: Number(btn.dataset.id) });
    } else if (act === "seed-reset-group-generations") {
      await api("/api/seeds/reset-group-generations", "POST", { group_id: Number(btn.dataset.id) });
    } else if (act === "seed-toggle-group") {
      const gid = Number(btn.dataset.id);
      seedGroupOpenById[gid] = !seedGroupOpenById[gid];
      saveObjectMapToStorage(SEED_GROUP_OPEN_STORAGE_KEY, seedGroupOpenById);
      const panel = document.getElementById(`seed_group_${gid}`);
      if (panel) panel.classList.toggle("open", !!seedGroupOpenById[gid]);
      btn.textContent = seedGroupOpenById[gid] ? "▾" : "▸";
      return;
    } else if (act === "seed-del-struct") {
      await api("/api/seeds/delete-structure", "POST", { group_id: Number(btn.dataset.id), index: Number(btn.dataset.idx) });
    } else if (act === "seed-toggle-struct") {
      const key = String(btn.dataset.key || "");
      if (!key) return;
      seedTextOpenByKey[key] = !seedTextOpenByKey[key];
      saveObjectMapToStorage(SEED_TEXT_OPEN_STORAGE_KEY, seedTextOpenByKey);
      const panel = document.getElementById(`seed_text_${key}`);
      if (panel) panel.classList.toggle("open", !!seedTextOpenByKey[key]);
      btn.textContent = `${seedTextOpenByKey[key] ? "▾" : "▸"} ${tr("structure_label")}`;
      return;
    } else if (act === "seed-copy-struct") {
      const gid = Number(btn.dataset.id);
      const idx = Number(btn.dataset.idx);
      const group = (appState?.seed_groups || []).find((x) => Number(x.id) === gid);
      const item = group?.structures?.[idx];
      const text = item?.structure || "";
      if (!text) throw new Error("Structure text is empty.");
      await navigator.clipboard.writeText(text);
      flash(tr("structure_copied"));
      return;
    } else if (act === "seed-viz-group") {
      const d = await api("/api/seeds/visualize-group", "POST", { group_id: Number(btn.dataset.id) });
      actionMessage = d.message || "";
      showTopToast(tr("visualizer_running"));
    } else if (act === "seed-viz-struct") {
      const d = await api("/api/seeds/visualize-structure", "POST", { group_id: Number(btn.dataset.id), index: Number(btn.dataset.idx) });
      actionMessage = d.message || "";
      showTopToast(tr("visualizer_running"));
    } else if (act === "anti-seed-del-group") {
      await api("/api/antiseeds/delete-group", "POST", { group_id: Number(btn.dataset.id) });
    } else if (act === "anti-seed-reset-group-generations") {
      await api("/api/antiseeds/reset-group-generations", "POST", { group_id: Number(btn.dataset.id) });
    } else if (act === "anti-seed-toggle-group") {
      const gid = Number(btn.dataset.id);
      antiSeedGroupOpenById[gid] = !antiSeedGroupOpenById[gid];
      saveObjectMapToStorage(ANTI_SEED_GROUP_OPEN_STORAGE_KEY, antiSeedGroupOpenById);
      const panel = document.getElementById(`anti_seed_group_${gid}`);
      if (panel) panel.classList.toggle("open", !!antiSeedGroupOpenById[gid]);
      btn.textContent = antiSeedGroupOpenById[gid] ? "▾" : "▸";
      return;
    } else if (act === "anti-seed-del-struct") {
      await api("/api/antiseeds/delete-structure", "POST", { group_id: Number(btn.dataset.id), index: Number(btn.dataset.idx) });
    } else if (act === "anti-seed-toggle-struct") {
      const key = String(btn.dataset.key || "");
      if (!key) return;
      antiSeedTextOpenByKey[key] = !antiSeedTextOpenByKey[key];
      saveObjectMapToStorage(ANTI_SEED_TEXT_OPEN_STORAGE_KEY, antiSeedTextOpenByKey);
      const panel = document.getElementById(`anti_seed_text_${key}`);
      if (panel) panel.classList.toggle("open", !!antiSeedTextOpenByKey[key]);
      btn.textContent = `${antiSeedTextOpenByKey[key] ? "▾" : "▸"} ${tr("structure_label")}`;
      return;
    } else if (act === "anti-seed-copy-struct") {
      const gid = Number(btn.dataset.id);
      const idx = Number(btn.dataset.idx);
      const group = (appState?.anti_seed_groups || []).find((x) => Number(x.id) === gid);
      const item = group?.structures?.[idx];
      const text = item?.structure || "";
      if (!text) throw new Error("Structure text is empty.");
      await navigator.clipboard.writeText(text);
      flash(tr("structure_copied"));
      return;
    } else if (act === "anti-seed-viz-group") {
      const d = await api("/api/antiseeds/visualize-group", "POST", { group_id: Number(btn.dataset.id) });
      actionMessage = d.message || "";
      showTopToast(tr("visualizer_running"));
    } else if (act === "anti-seed-viz-struct") {
      const d = await api("/api/antiseeds/visualize-structure", "POST", { group_id: Number(btn.dataset.id), index: Number(btn.dataset.idx) });
      actionMessage = d.message || "";
      showTopToast(tr("visualizer_running"));
    } else if (act === "preview-toggle") {
      const n = btn.dataset.n;
      const stage = Number(btn.dataset.stage);
      const path = btn.dataset.path;
      if (openPreviewByN[n] && openPreviewByN[n].stage === stage) delete openPreviewByN[n];
      else openPreviewByN[n] = { stage, path };
    } else if (act === "preview-viz") {
      const d = await api("/api/preview/visualize", "POST", { path: btn.dataset.path });
      actionMessage = d.message || "";
      showTopToast(tr("visualizer_running"));
    } else if (act === "browser-enter") {
      await loadBrowser(btn.dataset.path);
      return;
    } else if (act === "browser-read") {
      const path = String(btn.dataset.path || "");
      if (!path) return;
      if (browserFileOpenByPath[path]) {
        browserFileOpenByPath[path] = false;
        renderBrowserList(browserListingData);
        restoreBrowserPanelSizeIfNoOpenPreviews();
        return;
      }
      rememberBrowserPanelSize();
      const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".tiff", ".tif"]);
      const lowerPath = path.toLowerCase();
      const isImage = IMAGE_EXTS.has(lowerPath.slice(lowerPath.lastIndexOf(".")));
      if (!isImage && !(path in browserFileContentByPath)) {
        const d = await api("/api/browser/read", "POST", { path });
        browserFileContentByPath[path] = d.content || "";
      }
      browserFileOpenByPath[path] = true;
      renderBrowserList(browserListingData);
      flash(tr("file_opened"));
      return;
    } else if (act === "browser-viz") {
      const d = await api("/api/browser/visualize", "POST", { path: btn.dataset.path });
      actionMessage = d.message || "";
      showTopToast(tr("visualizer_running"));
    } else if (act === "browser-copy") {
      const path = String(btn.dataset.path || "");
      if (!path) return;
      let text = browserFileContentByPath[path];
      if (text === undefined) {
        const d = await api("/api/browser/read", "POST", { path });
        text = d.content || "";
        browserFileContentByPath[path] = text;
      }
      await navigator.clipboard.writeText(String(text || ""));
      btn.classList.add("copied");
      const prev = copyHintTimers.get(btn);
      if (prev) clearTimeout(prev);
      const t = setTimeout(() => {
        btn.classList.remove("copied");
        copyHintTimers.delete(btn);
      }, 1500);
      copyHintTimers.set(btn, t);
      flash(tr("file_copied"));
      return;
    } else if (act === "browser-seed-check") {
      const d = await api("/api/seeds/check", "POST", { path: btn.dataset.path });
      document.getElementById("browser_seed_check").textContent = formatSeedCheckInfo(d.info);
      return;
    } else if (act === "browser-seed-add") {
      await api("/api/seeds/add-path", "POST", { path: btn.dataset.path });
    } else if (act === "browser-anti-seed-add") {
      await api("/api/antiseeds/add-path", "POST", { path: btn.dataset.path });
    }
    await refreshState();
    flash(actionMessage || tr("done"));
  } catch (e) {
    flash(e.message, false);
  }
});

document.addEventListener("change", async (ev) => {
  const input = ev.target;
  if (!(input instanceof HTMLInputElement)) return;
  const act = input.dataset.act;
  if (!act) return;
  try {
    if (act === "seed-group-generation") {
      await api("/api/seeds/set-group-generation", "POST", {
        group_id: Number(input.dataset.id),
        generation: input.value,
      });
      await refreshState();
      flash(tr("done"));
    } else if (act === "seed-struct-generation") {
      await api("/api/seeds/set-structure-generation", "POST", {
        group_id: Number(input.dataset.id),
        index: Number(input.dataset.idx),
        generation: input.value,
      });
      await refreshState();
      flash(tr("done"));
    } else if (act === "anti-seed-group-generation") {
      await api("/api/antiseeds/set-group-generation", "POST", {
        group_id: Number(input.dataset.id),
        generation: input.value,
      });
      await refreshState();
      flash(tr("done"));
    } else if (act === "anti-seed-struct-generation") {
      await api("/api/antiseeds/set-structure-generation", "POST", {
        group_id: Number(input.dataset.id),
        index: Number(input.dataset.idx),
        generation: input.value,
      });
      await refreshState();
      flash(tr("done"));
    }
  } catch (e) {
    flash(e.message, false);
  }
});

document.addEventListener("input", (ev) => {
  const input = ev.target;
  if (!(input instanceof HTMLInputElement)) return;
  const act = input.dataset.act;
  if (!act) return;
  if (act === "seed-group-generation") {
    applyGroupGenerationLocally(Number(input.dataset.id), input.value);
    return;
  }
  if (act === "seed-struct-generation") {
    const gid = Number(input.dataset.id);
    const idx = Number(input.dataset.idx);
    const group = (appState?.seed_groups || []).find((g) => Number(g.id) === gid);
    const item = group?.structures?.[idx];
    if (item) {
      item.generation_user_set = true;
      item.seed_generation = input.value ? input.value : null;
    }
    return;
  }
  if (act === "anti-seed-group-generation") {
    applyAntiGroupGenerationLocally(Number(input.dataset.id), input.value);
    return;
  }
  if (act === "anti-seed-struct-generation") {
    const gid = Number(input.dataset.id);
    const idx = Number(input.dataset.idx);
    const group = (appState?.anti_seed_groups || []).find((g) => Number(g.id) === gid);
    const item = group?.structures?.[idx];
    if (item) {
      item.generation_user_set = true;
      item.seed_generation = input.value ? input.value : null;
    }
  }
});

document.addEventListener("focusin", (ev) => {
  const t = ev.target;
  if (!(t instanceof HTMLInputElement)) return;
  const act = t.dataset.act;
  if (act === "seed-group-generation" || act === "seed-struct-generation") {
    seedGenerationEditing = true;
  }
  if (act === "anti-seed-group-generation" || act === "anti-seed-struct-generation") {
    antiSeedGenerationEditing = true;
  }
});

document.addEventListener("focusout", async (ev) => {
  const t = ev.target;
  if (!(t instanceof HTMLInputElement)) return;
  const act = t.dataset.act;
  if (act === "seed-group-generation" || act === "seed-struct-generation") {
    seedGenerationEditing = false;
    try {
      await refreshState();
    } catch (_e) {}
  }
  if (act === "anti-seed-group-generation" || act === "anti-seed-struct-generation") {
    antiSeedGenerationEditing = false;
    try {
      await refreshState();
    } catch (_e) {}
  }
});

initializeModeAdvancedDefaults();
loadAdvGroupOpenState();
loadObjectMapFromStorage(SEED_GROUP_OPEN_STORAGE_KEY, seedGroupOpenById);
loadObjectMapFromStorage(SEED_TEXT_OPEN_STORAGE_KEY, seedTextOpenByKey);
loadObjectMapFromStorage(ANTI_SEED_GROUP_OPEN_STORAGE_KEY, antiSeedGroupOpenById);
loadObjectMapFromStorage(ANTI_SEED_TEXT_OPEN_STORAGE_KEY, antiSeedTextOpenByKey);
renderAdvancedFields();
bindAdvancedMultilineEditors();

const themeSelectEl = document.getElementById("ui_theme");
const langSelectEl = document.getElementById("ui_lang");
const storedTheme = localStorage.getItem(UI_THEME_STORAGE_KEY) || "Ocean";
const storedLang = localStorage.getItem(UI_LANG_STORAGE_KEY) || "ru";
if (themeSelectEl) themeSelectEl.value = storedTheme;
if (langSelectEl) langSelectEl.value = storedLang;
applyTheme(storedTheme);
applyLanguage(storedLang);
updateBoomButtons();
const boomBtnEl = document.getElementById("boom_btn");
if (boomBtnEl) {
  boomBtnEl.addEventListener("click", () => {
    if (currentUiTheme === "Sunset") {
      runSunsetEffect();
    } else if (currentUiTheme === "Deep Blue") {
      runWaveEffect();
    } else {
      runBoomEffect();
    }
  });
}
const heroEmojiEl = document.getElementById("hero_run_emoji");
if (heroEmojiEl) {
  heroEmojiEl.addEventListener("click", () => {
    document.getElementById("run_btn")?.click();
  });
}
window.addEventListener("resize", () => {
  if (boomLaunched) {
    fillBoomHearts();
    showBoomUSPEXCutout();
  }
  if (sunsetLaunched) {
    fillSunsetSand();
    showSunsetUSPEXCutout();
  }
  if (waveLaunched) {
    buildWaveBigSvg();
  }
});
window.addEventListener("scroll", () => {
  lastUserScrollAt = performance.now();
}, { passive: true });
if (themeSelectEl) {
  themeSelectEl.addEventListener("change", () => {
    const val = themeSelectEl.value || "Ocean";
    localStorage.setItem(UI_THEME_STORAGE_KEY, val);
    applyTheme(val);
  });
}
if (langSelectEl) {
  langSelectEl.addEventListener("change", async () => {
    const val = langSelectEl.value || "ru";
    localStorage.setItem(UI_LANG_STORAGE_KEY, val);
    applyLanguage(val);
    try {
      await refreshState(false, true);
      renderBrowserList(browserListingData);
    } catch (_e) {}
  });
}

document.getElementById("exe_path").addEventListener("input", queuePathAutoSave);
document.getElementById("stmng_exe_path").addEventListener("input", queuePathAutoSave);
document.getElementById("workdir").addEventListener("input", queuePathAutoSave);
document.getElementById("mp_api_key").addEventListener("input", queueMpAutoSave);
document.getElementById("mp_chemsys").addEventListener("input", queueMpAutoSave);
document.getElementById("mp_ehull_max").addEventListener("input", queueMpAutoSave);
document.getElementById("anti_mp_api_key").addEventListener("input", queueMpAutoSave);
document.getElementById("anti_mp_chemsys").addEventListener("input", queueMpAutoSave);
document.getElementById("anti_mp_ehull_max").addEventListener("input", queueMpAutoSave);
for (const id of [
  "mp_api_key",
  "mp_chemsys",
  "mp_ehull_max",
  "anti_mp_api_key",
  "anti_mp_chemsys",
  "anti_mp_ehull_max",
]) {
  const el = document.getElementById(id);
  if (!el) continue;
  el.addEventListener("change", async () => {
    try {
      await saveMpSettingsNow();
    } catch (e) {
      flash(e.message, false);
    }
  });
  el.addEventListener("blur", async () => {
    try {
      await saveMpSettingsNow();
    } catch (e) {
      flash(e.message, false);
    }
  });
}

document.getElementById("mode_fixed_btn").addEventListener("click", async () => {
  switchMode("fixed");
  const c = modeCache["fixed"];
  const needGenerate = !c.preview_text && !c.preview_dirty;
  await saveSettings(!needGenerate, needGenerate);
  await refreshState(true);
});
document.getElementById("mode_single_btn").addEventListener("click", async () => {
  switchMode("single");
  const c = modeCache["single"];
  const needGenerate = !c.preview_text && !c.preview_dirty;
  await saveSettings(!needGenerate, needGenerate);
  await refreshState(true);
});
document.getElementById("mode_variable_btn").addEventListener("click", async () => {
  switchMode("variable");
  const c = modeCache["variable"];
  const needGenerate = !c.preview_text && !c.preview_dirty;
  await saveSettings(!needGenerate, needGenerate);
  await refreshState(true);
});

document.getElementById("adv_toggle").addEventListener("change", async () => {
  const m = currentMode();
  modeCache[m].advanced_enabled = document.getElementById("adv_toggle").checked;
  updateModeVisibility();
  try {
    await saveSettings();
    await refreshState(true);
  } catch (e) {
    flash(e.message, false);
  }
});

for (const k of ADV_KEYS) {
  document.getElementById(`adv_${k}`).addEventListener("input", () => {
    const m = currentMode();
    const el = document.getElementById(`adv_${k}`);
    if (el instanceof HTMLTextAreaElement) autoSizeAdvTextarea(el);
    modeCache[m].advanced_params[k] = document.getElementById(`adv_${k}`).value;
    queuePreviewSync();
  });
}

for (const id of ["elements_text", "counts_text", "ratios_text", "min_at_text", "max_at_text"]) {
  document.getElementById(id).addEventListener("input", () => {
    readCurrentFormIntoModeCache();
    queuePreviewSync();
  });
}

document.getElementById("seed_check_path").addEventListener("click", async () => {
  try {
    const d = await api("/api/seeds/check", "POST", { path: document.getElementById("seed_path").value });
    const checkEl = document.getElementById("seed_check_result");
    checkEl.textContent = formatSeedCheckInfo(d.info);
    checkEl.style.display = "";
    flash(tr("checked"));
  } catch (e) {
    const checkEl = document.getElementById("seed_check_result");
    checkEl.textContent = e.message;
    checkEl.style.display = "";
    flash(e.message, false);
  }
});

document.getElementById("seed_add_path").addEventListener("click", async () => {
  try {
    await saveSettings();
    await api("/api/seeds/add-path", "POST", { path: document.getElementById("seed_path").value });
    document.getElementById("seed_path").value = "";
    const checkEl = document.getElementById("seed_check_result");
    checkEl.textContent = tr("check_hint");
    checkEl.style.display = "none";
    await refreshState(true);
    flash(tr("seed_added"));
  } catch (e) {
    flash(e.message, false);
  }
});

document.getElementById("seed_add_mp").addEventListener("click", async () => {
  setMpStatus("seed", "loading");
  try {
    await saveSettings();
    await api("/api/seeds/add-mp", "POST", {
      api_key: document.getElementById("mp_api_key").value,
      chemsys: document.getElementById("mp_chemsys").value,
      ehull: document.getElementById("mp_ehull_max").value,
    });
    await refreshState(true);
    setMpStatus("seed", "done");
    flash(tr("mp_seed_added"));
  } catch (e) {
    setMpStatus("seed", "hidden");
    flash(e.message, false);
  }
});

document.getElementById("anti_seed_check_path").addEventListener("click", async () => {
  try {
    const d = await api("/api/antiseeds/check", "POST", { path: document.getElementById("anti_seed_path").value });
    const checkEl = document.getElementById("anti_seed_check_result");
    checkEl.textContent = formatSeedCheckInfo(d.info);
    checkEl.style.display = "";
    flash(tr("checked"));
  } catch (e) {
    const checkEl = document.getElementById("anti_seed_check_result");
    checkEl.textContent = e.message;
    checkEl.style.display = "";
    flash(e.message, false);
  }
});

document.getElementById("anti_seed_add_path").addEventListener("click", async () => {
  try {
    await saveSettings();
    await api("/api/antiseeds/add-path", "POST", { path: document.getElementById("anti_seed_path").value });
    document.getElementById("anti_seed_path").value = "";
    const checkEl = document.getElementById("anti_seed_check_result");
    checkEl.textContent = tr("check_hint");
    checkEl.style.display = "none";
    await refreshState(true);
    flash(tr("antiseed_added"));
  } catch (e) {
    flash(e.message, false);
  }
});

document.getElementById("anti_seed_add_mp").addEventListener("click", async () => {
  setMpStatus("anti", "loading");
  try {
    await saveSettings();
    await api("/api/antiseeds/add-mp", "POST", {
      api_key: document.getElementById("anti_mp_api_key").value,
      chemsys: document.getElementById("anti_mp_chemsys").value,
      ehull: document.getElementById("anti_mp_ehull_max").value,
    });
    await refreshState(true);
    setMpStatus("anti", "done");
    flash(tr("mp_antiseed_added"));
  } catch (e) {
    setMpStatus("anti", "hidden");
    flash(e.message, false);
  }
});

async function openRunConfirmModal() {
  try {
    await saveSettings();
    const preview = document.getElementById("preview_text").value;
    const workdir = document.getElementById("workdir").value;
    document.getElementById("run_confirm_preview").textContent = preview;
    document.getElementById("run_confirm_workdir").textContent = workdir;
    document.getElementById("run_confirm_modal").style.display = "flex";
  } catch (e) {
    flash(e.message, false);
  }
}

document.getElementById("run_btn").addEventListener("click", () => {
  openRunConfirmModal();
});

document.getElementById("run_confirm_ok_btn").addEventListener("click", async () => {
  document.getElementById("run_confirm_modal").style.display = "none";
  try {
    await api("/api/run", "POST", {});
    flash(tr("run_started"));
  } catch (e) {
    flash(e.message, false);
  }
});

document.getElementById("run_confirm_close_btn").addEventListener("click", () => {
  document.getElementById("run_confirm_modal").style.display = "none";
});
document.getElementById("run_confirm_cancel_btn").addEventListener("click", () => {
  document.getElementById("run_confirm_modal").style.display = "none";
});
document.getElementById("run_confirm_modal").addEventListener("click", (ev) => {
  if (ev.target?.id === "run_confirm_modal") {
    ev.currentTarget.style.display = "none";
  }
});

document.getElementById("stop_btn").addEventListener("click", async () => {
  try {
    await api("/api/stop", "POST", {});
    flash(tr("stop_sent"));
  } catch (e) {
    flash(e.message, false);
  }
});

document.getElementById("browser_open").addEventListener("click", () => {
  browserOpenTyped();
});
document.getElementById("browser_current").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") browserOpenTyped();
});
document.getElementById("browser_up").addEventListener("click", async () => {
  try {
    if (!browserState.canGoUp) return;
    await loadBrowser(browserState.parent);
  } catch (e) {
    flash(e.message, false);
  }
});
document.getElementById("browser_root_btn").addEventListener("click", async () => {
  try {
    await loadBrowser(browserRoot());
  } catch (e) {
    flash(e.message, false);
  }
});

function showPrompt(title, defaultVal = "") {
  return new Promise(resolve => {
    const modal  = document.getElementById("prompt_modal");
    const titleEl = document.getElementById("prompt_modal_title");
    const input  = document.getElementById("prompt_modal_input");
    const okBtn  = document.getElementById("prompt_modal_ok");
    const cancelBtn = document.getElementById("prompt_modal_cancel");
    const closeBtn  = document.getElementById("prompt_modal_close");

    titleEl.textContent = title;
    input.value = defaultVal;
    modal.style.display = "flex";
    requestAnimationFrame(() => { input.focus(); input.select(); });

    const finish = (val) => {
      modal.style.display = "none";
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      closeBtn.removeEventListener("click", onCancel);
      input.removeEventListener("keydown", onKey);
      modal.removeEventListener("click", onBg);
      resolve(val);
    };
    const onOk     = () => finish(input.value.trim() || null);
    const onCancel = () => finish(null);
    const onKey    = (e) => { if (e.key === "Enter") onOk(); else if (e.key === "Escape") onCancel(); };
    const onBg     = (e) => { if (e.target === modal) onCancel(); };

    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
    closeBtn.addEventListener("click", onCancel);
    input.addEventListener("keydown", onKey);
    modal.addEventListener("click", onBg);
  });
}

document.getElementById("browser_mkdir_btn").addEventListener("click", async () => {
  const name = await showPrompt(tr("mkdir_prompt"));
  if (!name || !name.trim()) return;
  try {
    const root = browserRoot();
    const current = document.getElementById("browser_current").value.trim();
    await api("/api/browser/mkdir", "POST", { root, current, name: name.trim() });
    await loadBrowser();
  } catch (e) {
    flash(e.message, false);
  }
});

let ctxTargetPath = "";
document.getElementById("browser_dirs").addEventListener("contextmenu", (ev) => {
  const row = ev.target.closest("[data-path]");
  if (!row) return;
  ev.preventDefault();
  ctxTargetPath = row.dataset.path || "";
  const menu = document.getElementById("browser_ctx_menu");
  menu.style.display = "block";
  menu.style.left = `${ev.clientX}px`;
  menu.style.top = `${ev.clientY}px`;
});
document.addEventListener("click", (ev) => {
  const menu = document.getElementById("browser_ctx_menu");
  if (menu && !menu.contains(ev.target)) {
    menu.style.display = "none";
  }
});
document.getElementById("browser_ctx_rename").addEventListener("click", async () => {
  document.getElementById("browser_ctx_menu").style.display = "none";
  if (!ctxTargetPath) return;
  const newName = await showPrompt(tr("rename_prompt"), ctxTargetPath.split(/[\\/]/).pop());
  if (!newName) return;
  try {
    const root = browserRoot();
    await api("/api/browser/rename", "POST", { root, path: ctxTargetPath, new_name: newName });
    await loadBrowser();
  } catch (e) {
    flash(e.message, false);
  }
});

document.getElementById("browser_ctx_set_workdir").addEventListener("click", () => {
  document.getElementById("browser_ctx_menu").style.display = "none";
  if (!ctxTargetPath) return;
  document.getElementById("workdir").value = ctxTargetPath;
  queuePathAutoSave();
});

document.getElementById("preview_text").addEventListener("input", () => {
  const m = currentMode();
  modeCache[m].preview_text = document.getElementById("preview_text").value;
  modeCache[m].preview_dirty = modeCache[m].preview_text !== expectedPreviewText;
  updatePreviewDirtyUI();
});

document.getElementById("preview_reset_btn").addEventListener("click", async () => {
  document.getElementById("preview_text").value = expectedPreviewText;
  updatePreviewDirtyUI();
  try {
    await saveSettings();
    await refreshState(true);
  } catch (e) {
    flash(e.message, false);
  }
});

document.getElementById("seeds_enabled").addEventListener("change", () => {
  updateSeedsVisibility();
});
document.getElementById("anti_seeds_enabled").addEventListener("change", () => {
  updateAntiSeedsVisibility();
});

document.getElementById("preview_results_toggle").addEventListener("click", () => {
  const wrap = document.getElementById("preview_results_wrap");
  const btn = document.getElementById("preview_results_toggle");
  const collapsed = wrap.classList.toggle("collapsed");
  btn.textContent = collapsed ? "▸" : "▾";
  btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
});

document.getElementById("paths_toggle").addEventListener("click", () => {
  const wrap = document.getElementById("paths_wrap");
  const btn = document.getElementById("paths_toggle");
  const collapsed = wrap.classList.toggle("collapsed");
  btn.textContent = collapsed ? "▸" : "▾";
  btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
});

document.getElementById("browser_toggle").addEventListener("click", () => {
  const wrap = document.getElementById("browser_wrap");
  const btn = document.getElementById("browser_toggle");
  const collapsed = wrap.classList.toggle("collapsed");
  btn.textContent = collapsed ? "▸" : "▾";
  btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
});

document.getElementById("mode_toggle").addEventListener("click", () => {
  const wrap = document.getElementById("mode_wrap");
  const btn = document.getElementById("mode_toggle");
  const collapsed = wrap.classList.toggle("collapsed");
  btn.textContent = collapsed ? "▸" : "▾";
  btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
});

document.getElementById("specific_open_btn").addEventListener("click", () => {
  const modal = document.getElementById("specific_modal");
  if (!modal) return;
  renderSpecificModal();
  modal.style.display = "flex";
});
document.getElementById("specific_close_btn").addEventListener("click", () => {
  const modal = document.getElementById("specific_modal");
  if (!modal) return;
  modal.style.display = "none";
});
document.getElementById("specific_modal").addEventListener("click", (ev) => {
  if (ev.target?.id === "specific_modal") {
    ev.currentTarget.style.display = "none";
  }
});
document.getElementById("specific_enabled").addEventListener("change", async (ev) => {
  const checked = !!ev.target?.checked;
  specificEnabled = checked;
  try {
    if (checked) {
      await maybeLoadSpecificFromWorkdirOnEnable();
    }
    await syncSpecificSettings();
    renderSpecificModal();
  } catch (e) {
    flash(e.message, false);
  }
});
document.getElementById("specific_add_defaults_btn").addEventListener("click", async () => {
  try {
    await addDefaultSpecificFiles("add");
    await syncSpecificSettings();
  } catch (e) {
    flash(e.message, false);
  }
});
document.getElementById("specific_add_file_btn").addEventListener("click", async () => {
  const nextIdx = specificFiles.length + 1;
  specificFiles.push({ name: `new_file_${nextIdx}.yaml`, content: "" });
  specificNameEditingIndex = specificFiles.length - 1;
  if (specificEditorIndex < 0) specificEditorIndex = specificFiles.length - 1;
  renderSpecificModal();
  queueSpecificSave();
});
document.getElementById("specific_files_list").addEventListener("click", async (ev) => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  const act = btn.dataset.specificAct;
  const idx = Number(btn.dataset.idx);
  if (!Number.isFinite(idx) || idx < 0 || idx >= specificFiles.length) return;
  if (act === "del") {
    specificFiles.splice(idx, 1);
    if (specificEditorIndex === idx) specificEditorIndex = -1;
    if (specificEditorIndex > idx) specificEditorIndex -= 1;
    if (specificNameEditingIndex === idx) specificNameEditingIndex = -1;
    renderSpecificModal();
    queueSpecificSave();
    return;
  }
  if (act === "view") {
    specificEditorIndex = idx;
    renderSpecificModal();
    return;
  }
});
document.getElementById("specific_files_list").addEventListener("dblclick", (ev) => {
  const btn = ev.target.closest('button[data-specific-act="name"]');
  if (!btn) return;
  const idx = Number(btn.dataset.idx);
  if (!Number.isFinite(idx) || idx < 0 || idx >= specificFiles.length) return;
  specificNameEditingIndex = idx;
  renderSpecificModal();
});
document.getElementById("specific_files_list").addEventListener("keydown", (ev) => {
  const input = ev.target;
  if (!(input instanceof HTMLInputElement)) return;
  if (input.dataset.specificAct !== "rename-input") return;
  if (ev.key !== "Enter") return;
  const idx = Number(input.dataset.idx);
  if (!Number.isFinite(idx) || idx < 0 || idx >= specificFiles.length) return;
  const nextName = String(input.value || "").trim();
  if (nextName) specificFiles[idx].name = nextName.replaceAll("/", "_").replaceAll("\\", "_");
  specificNameEditingIndex = -1;
  renderSpecificModal();
  queueSpecificSave();
});
document.getElementById("specific_files_list").addEventListener("focusout", (ev) => {
  const input = ev.target;
  if (!(input instanceof HTMLInputElement)) return;
  if (input.dataset.specificAct !== "rename-input") return;
  const idx = Number(input.dataset.idx);
  if (!Number.isFinite(idx) || idx < 0 || idx >= specificFiles.length) return;
  const nextName = String(input.value || "").trim();
  if (nextName) specificFiles[idx].name = nextName.replaceAll("/", "_").replaceAll("\\", "_");
  specificNameEditingIndex = -1;
  renderSpecificModal();
  queueSpecificSave();
});
document.getElementById("specific_editor_text").addEventListener("input", (ev) => {
  if (specificEditorIndex < 0 || specificEditorIndex >= specificFiles.length) return;
  specificFiles[specificEditorIndex].content = ev.target.value || "";
  queueSpecificSave();
});

document.getElementById("seed_check_result").style.display = "none";
document.getElementById("anti_seed_check_result").style.display = "none";
document.getElementById("log_text").addEventListener("focus", (ev) => {
  const el = ev.target;
  if (el instanceof HTMLTextAreaElement && el.readOnly) {
    // Keep log selectable, but avoid sticky focus causing page scroll jumps.
    el.blur();
  }
});

document.querySelector('a[href="/StructureCollection/site/"]')?.addEventListener("click", (e) => {
  e.preventDefault();
  const url = `${location.protocol}//${location.host}/StructureCollection/site/`;
  if (window.__TAURI__?.shell) {
    window.__TAURI__.shell.open(url);
  } else {
    window.open(url, "_blank");
  }
});

setInterval(() => refreshState(false, true), 3000);
setInterval(pollLog, 1000);
refreshState(true);
