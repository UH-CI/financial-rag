import React, { useState, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { getRefBotResults, uploadRefBotCollection, deleteRefBotResult, getRefBotConstraints, addRefBotConstraint, updateRefBotConstraint, deleteRefBotConstraint } from '../../services/api';
import AppHeader from '../layout/AppHeader';

interface CommitteeInfo {
    committee_id: string;
    committee_name: string;
    description: string;
}

const COMMITTEE_LEGEND: CommitteeInfo[] = [
    {
        "committee_id": "AGR",
        "committee_name": "Agriculture & Food Systems",
        "description": "Department of Agriculture, agriculture, aquaculture, crop and livestock production, food production and distribution, agricultural parks, animal welfare, invasive species"
    },
    {
        "committee_id": "CPC",
        "committee_name": "Consumer Protection & Commerce",
        "description": "Consumer protection, DCCA, trade, business, utilities, Landlord-Tenant Code, condominiums, insurance, financial institutions"
    },
    {
        "committee_id": "CAA",
        "committee_name": "Culture & Arts",
        "description": "Hawaii's multi-cultural heritage, State Foundation on Culture and the Arts"
    },
    {
        "committee_id": "ECD",
        "committee_name": "Economic Development & Technology",
        "description": "Job creation, public-private partnerships, new industry, broadband, technology, cybersecurity"
    },
    {
        "committee_id": "EDN",
        "committee_name": "Education",
        "description": "Early childhood education, primary and secondary schools, libraries"
    },
    {
        "committee_id": "EEP",
        "committee_name": "Energy & Environmental Protection",
        "description": "Energy resources, utilities, climate change mitigation, environmental health, natural resources protection"
    },
    {
        "committee_id": "FIN",
        "committee_name": "Finance",
        "description": "State financing policies, taxation, budget, procurement"
    },
    {
        "committee_id": "HLT",
        "committee_name": "Health",
        "description": "General health, hospitals, community health care facilities, communicable diseases"
    },
    {
        "committee_id": "HED",
        "committee_name": "Higher Education",
        "description": "University of Hawaii, community colleges, post-secondary education"
    },
    {
        "committee_id": "HSG",
        "committee_name": "Housing",
        "description": "Housing development financing, affordable and rental housing, public housing"
    },
    {
        "committee_id": "HSH",
        "committee_name": "Human Services & Homelessness",
        "description": "Financial assistance, medical assistance, social welfare, elderly and youth services, homeless services"
    },
    {
        "committee_id": "JHA",
        "committee_name": "Judiciary & Hawaiian Affairs",
        "description": "Courts, crime prevention, police, civil law, individual rights, Hawaiian Home Lands, OHA"
    },
    {
        "committee_id": "LAB",
        "committee_name": "Labor",
        "description": "Employment, government operations, employee benefits, collective bargaining, workers' compensation"
    },
    {
        "committee_id": "LMG",
        "committee_name": "Legislative Management",
        "description": "House administrative operations, Legislative Reference Bureau, Auditor, Ombudsman"
    },
    {
        "committee_id": "PBS",
        "committee_name": "Public Safety",
        "description": "Corrections, rehabilitation, military facilities, emergency management"
    },
    {
        "committee_id": "TOU",
        "committee_name": "Tourism",
        "description": "Hawaii Convention Center, HVCB, HTA"
    },
    {
        "committee_id": "TRN",
        "committee_name": "Transportation",
        "description": "Air, water, and ground transportation, infrastructure"
    },
    {
        "committee_id": "WAL",
        "committee_name": "Water & Land",
        "description": "Climate adaptation, land and water resource administration, coastal lands, State parks, ocean activities"
    }
];

interface AnalysisResult {
    filename: string;
    name: string;
    item_count: number;
    data: any[];
    metadata?: any;
    created_at: number;
    error?: string;
}

interface JobInfo {
    job_id: string;
    name: string;
    status: string;
    enqueued_at: string;
}

// Deterministic color mapping for committeess
const getCommitteeColorStyle = (id: string) => {
    const colors = [
        'bg-red-100 text-red-800 border-red-200',
        'bg-orange-100 text-orange-800 border-orange-200',
        'bg-amber-100 text-amber-800 border-amber-200',
        'bg-yellow-100 text-yellow-800 border-yellow-200',
        'bg-lime-100 text-lime-800 border-lime-200',
        'bg-green-100 text-green-800 border-green-200',
        'bg-emerald-100 text-emerald-800 border-emerald-200',
        'bg-teal-100 text-teal-800 border-teal-200',
        'bg-cyan-100 text-cyan-800 border-cyan-200',
        'bg-sky-100 text-sky-800 border-sky-200',
        'bg-blue-100 text-blue-800 border-blue-200',
        'bg-indigo-100 text-indigo-800 border-indigo-200',
        'bg-violet-100 text-violet-800 border-violet-200',
        'bg-purple-100 text-purple-800 border-purple-200',
        'bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200',
        'bg-pink-100 text-pink-800 border-pink-200',
        'bg-rose-100 text-rose-800 border-rose-200',
    ];

    // Simple hash
    let hash = 0;
    for (let i = 0; i < id.length; i++) {
        hash = id.charCodeAt(i) + ((hash << 5) - hash);
    }

    const index = Math.abs(hash) % colors.length;
    return colors[index];
};

const RefBotPage: React.FC = () => {
    const [activeTab, setActiveTab] = useState<string | null>(null);
    const [resultsList, setResultsList] = useState<AnalysisResult[]>([]);
    const [jobsList, setJobsList] = useState<JobInfo[]>([]);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [metadataModalOpen, setMetadataModalOpen] = useState(false);

    // Upload State

    // Upload State
    const [name, setName] = useState('');
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);

    // Constraints State
    const [constraints, setConstraints] = useState<any[]>([]);
    const [loadingConstraints, setLoadingConstraints] = useState(false);
    const [newConstraintText, setNewConstraintText] = useState('');
    const [editingConstraintIndex, setEditingConstraintIndex] = useState<number | null>(null);
    const [editingConstraintText, setEditingConstraintText] = useState('');



    const { getAccessTokenSilently } = useAuth0();

    const getAuthToken = async () => {
        try {
            return await getAccessTokenSilently({
                authorizationParams: {
                    audience: 'https://api.financial-rag.com',
                    scope: 'openid profile email offline_access'
                }
            });
        } catch (error) {
            console.error("Error getting auth token", error);
            return null;
        }
    };

    const fetchResults = async () => {
        try {
            const token = await getAuthToken();
            if (!token) return;

            const data = await getRefBotResults(token);

            // Handle new format { completed: [], jobs: [] }
            let completed = [];
            let jobs = [];

            if (data.completed) {
                completed = data.completed;
                jobs = data.jobs || [];
            } else if (Array.isArray(data)) {
                // Fallback for legacy array response
                completed = data;
            }

            setResultsList(completed);
            setJobsList(jobs);

            if (completed.length > 0 && !activeTab) {
                setActiveTab(completed[0].filename); // Select most recent by default
            } else if (completed.length > 0 && activeTab) {
                // Keep active tab if it still exists
                const exists = completed.find((r: AnalysisResult) => r.filename === activeTab);
                if (!exists) setActiveTab(completed[0].filename);
            }
        } catch (e) {
            console.error("Failed to fetch results", e);
        }
    };

    // Auto-refresh if there are active jobs
    useEffect(() => {
        fetchResults(); // Initial fetch

        let interval: any;
        if (jobsList.length > 0) {
            interval = setInterval(fetchResults, 5000);
        }
        return () => {
            if (interval) clearInterval(interval);
        };
    }, [jobsList.length]); // Re-evaluate when job count changes

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setFile(e.target.files[0]);
        }
    };

    const fetchConstraints = async () => {
        try {
            setLoadingConstraints(true);
            const token = await getAuthToken();
            if (!token) return;
            const data = await getRefBotConstraints(token);
            setConstraints(data);
        } catch (e) {
            console.error("Failed to fetch constraints", e);
        } finally {
            setLoadingConstraints(false);
        }
    };

    useEffect(() => {
        if (isModalOpen) {
            fetchConstraints();
        }
    }, [isModalOpen]);

    const handleAddConstraint = async () => {
        if (!newConstraintText.trim()) return;
        try {
            const token = await getAuthToken();
            if (!token) return;
            await addRefBotConstraint(token, newConstraintText);
            setNewConstraintText('');
            await fetchConstraints();
        } catch (e) {
            console.error("Failed to add constraint", e);
            alert("Failed to add constraint");
        }
    };

    const handleUpdateConstraint = async (index: number) => {
        if (!editingConstraintText.trim()) return;
        try {
            const token = await getAuthToken();
            if (!token) return;
            await updateRefBotConstraint(token, index, editingConstraintText);
            setEditingConstraintIndex(null);
            setEditingConstraintText('');
            await fetchConstraints();
        } catch (e) {
            console.error("Failed to update constraint", e);
            alert("Failed to update constraint");
        }
    };

    const handleDeleteConstraint = async (index: number) => {
        if (!confirm("Are you sure you want to delete this constraint?")) return;
        try {
            const token = await getAuthToken();
            if (!token) return;
            await deleteRefBotConstraint(token, index);
            await fetchConstraints();
        } catch (e) {
            console.error("Failed to delete constraint", e);
            alert("Failed to delete constraint");
        }
    };

    const startEditing = (index: number, text: string) => {
        setEditingConstraintIndex(index);
        setEditingConstraintText(text);
    };

    const cancelEditing = () => {
        setEditingConstraintIndex(null);
        setEditingConstraintText('');
    };

    const handleUpload = async (e: React.FormEvent) => {
        e.preventDefault();

        if (editingConstraintIndex !== null) {
            alert("You need to save or cancel the constraint edit before you can submit a job.");
            return;
        }

        if (!name || !file) {
            setUploadError('Please provide both a name and a zip file.');
            return;
        }

        setUploading(true);
        setUploadError(null);

        const formData = new FormData();
        formData.append('name', name);
        formData.append('file', file);

        try {
            const token = await getAuthToken();
            if (!token) throw new Error("Authentication failed");

            await uploadRefBotCollection(token, name, file);

            // Close modal and refresh immediately to show queue status
            setIsModalOpen(false);
            setName('');
            setFile(null);
            await fetchResults();

        } catch (err: any) {
            setUploadError(err.message || 'An unknown error occurred');
        } finally {
            setUploading(false);
        }
    };

    const handleDelete = async (filename: string, e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent tab switching
        if (!confirm(`Are you sure you want to delete "${filename}" and its data?`)) {
            return;
        }

        try {
            const token = await getAuthToken();
            if (!token) return;

            await deleteRefBotResult(token, filename);

            // If the deleted tab was active, clear it so the next fetch selects a default
            if (activeTab === filename) {
                setActiveTab(null);
            }
            await fetchResults();

        } catch (error) {
            console.error("Error deleting result:", error);
            alert("Error deleting result.");
        }
    };

    const currentResult = resultsList.find(r => r.filename === activeTab);

    const cleanBillName = (name: string) => {
        if (!name) return "Unknown";
        // Handle various formats:
        // 1. HB 1234.pdf -> HB 1234
        // 2. HB_1234_ver.pdf -> HB
        // User requested split by "." then first index.
        // But also we want to keep previous underscore logic if valid?
        // Let's chain them carefully.
        // If it has underscore, maybe we still want that split? 
        // Example: "HB_2704.pdf" -> "HB" might be too aggressive if they want "HB 2704".
        // Let's try just splitting by "." first as requested for the PDF extension removal case.
        let clean = name;

        // Remove extension
        if (clean.includes('.')) {
            clean = clean.split('.')[0];
        }

        // If it looks like a file name with underscores for metadata (e.g. BillName_Timestamp), split it.
        // But if it's "HB_2704" maybe we keep it? 
        // User said: "Some bills don't have an underscore... Maybe as a second step, add a split by '.', then take the first index."

        // So for "HB 2704.pdf", split('.') -> "HB 2704".
        // For "HB_2704_processed.json", split('.') -> "HB_2704_processed". Then split('_')?

        // The safest approach for "Bill Name" display:
        // Just remove the extension.
        // Then if there is a CLEAR separator that denotes "junk" afterwards, remove it.

        // Let's stick to the user's specific request: "add a split by '.', then take the first index".
        // This effectively removes the extension.
        // We will ALSO keep the underscore split if it was there, assuming it strips timestamps or hashes.

        return clean.split('_')[0];
    };

    const downloadCSV = () => {
        if (!currentResult || !currentResult.data) return;

        // Define CSV headers
        const headers = ['Bill Name', 'Committees'];

        // Map data to CSV rows
        const rows = currentResult.data.map((item: any) => {
            const billName = cleanBillName(item.bill_name);
            const committees = item.committees ? item.committees.join(', ') : '';
            // Escape quotes if needed, though simple names usually don't need it
            return `"${billName}","${committees}"`;
        });

        // Combine headers and rows
        const csvContent = [
            headers.join(','),
            ...rows
        ].join('\n');

        // Create blob and download link
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', `${currentResult.name || 'export'}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col">
            <AppHeader />

            <main className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">

                {/* Legend */}
                <div className="mb-6 bg-white p-4 rounded-lg shadow-sm border border-gray-200">
                    <h3 className="text-sm font-semibold text-gray-700 mb-2 uppercase tracking-wide">Committee Legend</h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-x-4 gap-y-2">
                        {COMMITTEE_LEGEND.map(c => {
                            const colorStyle = getCommitteeColorStyle(c.committee_id);
                            // Extract just the text color part for the ID (e.g. text-red-800)
                            const textColor = colorStyle.match(/text-\w+-\d+/)?.[0] || 'text-blue-800';

                            return (
                                <div key={c.committee_id} className="text-xs group relative cursor-help flex items-center">
                                    <span className={`font-bold ${textColor} w-8 flex-shrink-0`}>{c.committee_id}</span>
                                    <span className="text-gray-400 mx-1">:</span>
                                    <div className="flex-1 min-w-0">
                                        <div className="text-gray-600 truncate">{c.committee_name}</div>
                                    </div>
                                    {/* Enhanced tooltip */}
                                    <div className="absolute bottom-full left-0 w-80 p-3 bg-gray-900 text-white text-xs rounded shadow-xl hidden group-hover:block z-50 mb-2 leading-relaxed whitespace-normal border border-gray-700">
                                        <div className="font-bold text-sm mb-1 text-white border-b border-gray-700 pb-1">{c.committee_name}</div>
                                        <div className="text-gray-300 mt-1">{c.description}</div>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>

                <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden min-h-[500px]">
                    {/* Tabs Header */}
                    <div className="bg-gray-100 border-b border-gray-200 flex items-center justify-between px-2 pt-2">
                        <div className="flex space-x-1 overflow-x-auto no-scrollbar scroll-smooth items-end flex-grow">
                            {/* Render Jobs First */}
                            {jobsList.map((job) => (
                                <div
                                    key={job.job_id}
                                    className="px-4 py-4 text-sm font-medium rounded-t-md border-t border-l border-r whitespace-nowrap bg-blue-50 border-blue-100 text-blue-700 mb-1 flex items-center opacity-80"
                                    title={`Status: ${job.status}`}
                                >
                                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    {job.name} <span className="ml-1 text-xs opacity-60">({job.status})</span>
                                </div>
                            ))}

                            {resultsList.map((res) => (
                                <div key={res.filename} className="relative group inline-flex">
                                    <button
                                        onClick={() => setActiveTab(res.filename)}
                                        className={`
                                     px-4 py-4 text-sm font-medium rounded-t-md border-t border-l border-r whitespace-nowrap transition-all duration-200 pr-16
                                    ${activeTab === res.filename
                                                ? 'bg-white border-gray-200 text-blue-700 border-b-white z-10 shadow-sm'
                                                : 'bg-gray-200 border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-100 mb-1'
                                            }
                                `}
                                    >
                                        {res.name} <span className="ml-1 text-xs opacity-60">({res.item_count})</span>
                                    </button>

                                    {/* Info Button - Only active tab */}
                                    {activeTab === res.filename && (
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setMetadataModalOpen(true);
                                            }}
                                            className="absolute right-7 top-3 p-1 rounded-full text-blue-500 hover:text-blue-700 hover:bg-blue-50 z-20 transition-opacity"
                                            title="See Details"
                                        >
                                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                        </button>
                                    )}

                                    <button
                                        onClick={(e) => handleDelete(res.filename, e)}
                                        className={`absolute right-1 top-3 p-1 rounded-full text-gray-400 hover:text-red-500 hover:bg-gray-100 
                                            ${activeTab === res.filename ? 'opacity-100 z-20' : 'opacity-0 group-hover:opacity-100'} transition-opacity`}
                                        title="Delete dataset"
                                    >
                                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                </div>
                            ))}

                            {resultsList.length === 0 && jobsList.length === 0 && (
                                <div className="px-4 py-2 text-sm text-gray-500 italic">No datasets found</div>
                            )}
                        </div>

                        {/* Actions Area */}
                        <div className="flex items-center space-x-2 pl-2 mb-1">
                            {/* Export CSV Button */}
                            {currentResult && (
                                <button
                                    onClick={downloadCSV}
                                    className="p-1.5 rounded-full bg-gray-100 text-gray-600 hover:bg-gray-200 hover:text-gray-800 shadow-sm transition-colors border border-gray-300"
                                    title="Export as CSV"
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                    </svg>
                                </button>
                            )}



                            {/* Add new button */}
                            <button
                                onClick={() => setIsModalOpen(true)}
                                className="p-1.5 rounded-full bg-blue-600 text-white hover:bg-blue-700 shadow-sm transition-colors flex-shrink-0"
                                title="Add new dataset"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                                </svg>
                            </button>
                        </div>
                    </div>

                    {/* Content Area */}
                    <div className="p-0">
                        {currentResult ? (
                            currentResult.error ? (
                                <div className="p-8 text-center text-red-500">
                                    Failed to load data: {currentResult.error}
                                </div>
                            ) : (
                                <div className="overflow-auto max-h-[calc(100vh-400px)] border-t border-gray-200">
                                    <table className="min-w-full divide-y divide-gray-200">
                                        <thead className="bg-gray-50 sticky top-0 z-20 shadow-sm">
                                            <tr>
                                                <th scope="col" className="px-6 py-3 text-left text-xs font-bold text-gray-700 uppercase tracking-wider w-1/4">
                                                    Bill Name
                                                </th>
                                                <th scope="col" className="px-6 py-3 text-left text-xs font-bold text-gray-700 uppercase tracking-wider w-3/4">
                                                    Committees
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody className="bg-white divide-y divide-gray-200">
                                            {currentResult.data?.sort((a: any, b: any) => {
                                                const nameA = cleanBillName(a.bill_name);
                                                const nameB = cleanBillName(b.bill_name);

                                                // Extract numbers
                                                const numA = parseInt(nameA.replace(/\D/g, '')) || 0;
                                                const numB = parseInt(nameB.replace(/\D/g, '')) || 0;

                                                // Sort by number
                                                if (numA !== numB) return numA - numB;

                                                // Fallback to string comparison
                                                return nameA.localeCompare(nameB);
                                            }).map((item: any, idx: number) => {
                                                // Actually let's use hover effect mainly.

                                                return (
                                                    <tr key={idx} className="hover:bg-gray-50 transition-colors">
                                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 border-r border-gray-100">
                                                            {cleanBillName(item.bill_name)}
                                                        </td>
                                                        <td className="px-6 py-4">
                                                            <div className="flex flex-wrap gap-2">
                                                                {item.committees && item.committees.length > 0 ? (
                                                                    item.committees.map((committeeId: string) => {
                                                                        const committeeInfo = COMMITTEE_LEGEND.find(c => c.committee_id === committeeId);
                                                                        const colorStyle = getCommitteeColorStyle(committeeId);

                                                                        return (
                                                                            <span
                                                                                key={committeeId}
                                                                                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${colorStyle} cursor-help`}
                                                                                title={committeeInfo ? `${committeeInfo.committee_name}: ${committeeInfo.description}` : committeeId}
                                                                            >
                                                                                {committeeId}
                                                                            </span>
                                                                        );
                                                                    })
                                                                ) : (
                                                                    <span className="text-gray-400 text-xs italic">No committees assigned</span>
                                                                )}
                                                            </div>
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                    {currentResult.data?.length === 0 && (
                                        <div className="p-12 text-center text-gray-400">
                                            No entries in this dataset.
                                        </div>
                                    )}
                                </div>
                            )
                        ) : (
                            <div className="p-12 text-center text-gray-500">
                                {resultsList.length === 0 ? "No datasets available. Click '+' to upload one." : "Select a tab to view results."}
                            </div>
                        )}
                    </div>
                </div>

                {/* Modal */}
                {
                    isModalOpen && (
                        <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
                            <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
                                <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" onClick={() => !uploading && setIsModalOpen(false)}></div>
                                <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

                                <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full sm:p-6">
                                    <div className="sm:flex sm:items-start">
                                        <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-blue-100 sm:mx-0 sm:h-10 sm:w-10">
                                            <svg className="h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                            </svg>
                                        </div>
                                        <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left w-full">
                                            <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                                                Upload New Collection
                                            </h3>
                                            <div className="mt-2">
                                                <p className="text-sm text-gray-500 mb-4">
                                                    Create a new dataset by uploading a ZIP file containing bill PDFs.
                                                </p>

                                                <form onSubmit={handleUpload} className="space-y-4">
                                                    <div>
                                                        <label htmlFor="name" className="block text-sm font-medium text-gray-700">Dataset Name</label>
                                                        <input
                                                            type="text"
                                                            id="name"
                                                            value={name}
                                                            onChange={(e) => setName(e.target.value)}
                                                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                                                            placeholder="e.g. Session 2024 Batch 1"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label htmlFor="file" className="block text-sm font-medium text-gray-700">Zip File</label>
                                                        <input
                                                            type="file"
                                                            id="file"
                                                            accept=".zip"
                                                            onChange={handleFileChange}
                                                            className="mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                                                        />
                                                    </div>

                                                    <div className="border-t border-gray-200 pt-4 mt-4">
                                                        <h4 className="text-sm font-medium text-gray-900 mb-2">Processing Constraints</h4>
                                                        <p className="text-xs text-gray-500 mb-3">
                                                            Define the rules for committee assignment. These constraints will be used by the AI Model.
                                                        </p>

                                                        {loadingConstraints ? (
                                                            <div className="text-sm text-gray-500 italic">Loading constraints...</div>
                                                        ) : (
                                                            <div className="space-y-3 max-h-96 overflow-y-auto mb-4 pr-1">
                                                                {constraints.map((c, idx) => (
                                                                    <div key={idx} className="flex items-start bg-gray-50 p-2 rounded border border-gray-200">
                                                                        <div className="flex-shrink-0 mr-2 mt-0.5 text-xs font-bold text-gray-400 w-5">
                                                                            {idx + 1}.
                                                                        </div>

                                                                        <div className="flex-grow min-w-0">
                                                                            {editingConstraintIndex === idx ? (
                                                                                <textarea
                                                                                    value={editingConstraintText}
                                                                                    onChange={(e) => setEditingConstraintText(e.target.value)}
                                                                                    className="w-full text-sm border-gray-300 rounded p-1 focus:ring-blue-500 focus:border-blue-500"
                                                                                    rows={2}
                                                                                />
                                                                            ) : (
                                                                                <div className="text-sm text-gray-700 whitespace-pre-wrap break-words">
                                                                                    {c.text}
                                                                                </div>
                                                                            )}
                                                                        </div>

                                                                        <div className="flex-shrink-0 ml-2 flex space-x-1">
                                                                            {editingConstraintIndex === idx ? (
                                                                                <>
                                                                                    <button
                                                                                        type="button"
                                                                                        onClick={() => handleUpdateConstraint(idx)}
                                                                                        className="text-green-600 hover:text-green-800 p-1"
                                                                                        title="Save"
                                                                                    >
                                                                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                                                                        </svg>
                                                                                    </button>
                                                                                    <button
                                                                                        type="button"
                                                                                        onClick={cancelEditing}
                                                                                        className="text-gray-500 hover:text-gray-700 p-1"
                                                                                        title="Cancel"
                                                                                    >
                                                                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                                                                        </svg>
                                                                                    </button>
                                                                                </>
                                                                            ) : (
                                                                                <>
                                                                                    <button
                                                                                        type="button"
                                                                                        onClick={() => startEditing(idx, c.text)}
                                                                                        className="text-blue-500 hover:text-blue-700 p-1"
                                                                                        title="Edit"
                                                                                        disabled={uploading}
                                                                                    >
                                                                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                                                                        </svg>
                                                                                    </button>
                                                                                    <button
                                                                                        type="button"
                                                                                        onClick={() => handleDeleteConstraint(idx)}
                                                                                        className="text-red-500 hover:text-red-700 p-1"
                                                                                        title="Delete"
                                                                                        disabled={uploading}
                                                                                    >
                                                                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                                                        </svg>
                                                                                    </button>
                                                                                </>
                                                                            )}
                                                                        </div>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}

                                                        <div className="flex items-center space-x-2">
                                                            <input
                                                                type="text"
                                                                value={newConstraintText}
                                                                onChange={(e) => setNewConstraintText(e.target.value)}
                                                                className="flex-grow text-sm border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                                                                placeholder="Add a new constraint..."
                                                                disabled={uploading}
                                                            />
                                                            <button
                                                                type="button"
                                                                onClick={handleAddConstraint}
                                                                disabled={!newConstraintText.trim() || uploading}
                                                                className="inline-flex items-center p-2 border border-transparent rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                                                            >
                                                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                                                                </svg>
                                                            </button>
                                                        </div>
                                                    </div>

                                                    {uploadError && (
                                                        <div className="text-red-500 text-sm">{uploadError}</div>
                                                    )}

                                                    <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                                                        <button
                                                            type="submit"
                                                            disabled={uploading}
                                                            className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-blue-600 text-base font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50"
                                                        >
                                                            {uploading ? 'Processing...' : 'Upload'}
                                                        </button>
                                                        <button
                                                            type="button"
                                                            onClick={() => setIsModalOpen(false)}
                                                            disabled={uploading}
                                                            className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:mt-0 sm:w-auto sm:text-sm"
                                                        >
                                                            Cancel
                                                        </button>
                                                    </div>
                                                </form>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )
                }
                {/* Metadata Modal */}
                {
                    metadataModalOpen && currentResult && (
                        <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="metadata-modal-title" role="dialog" aria-modal="true">
                            <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
                                <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" onClick={() => setMetadataModalOpen(false)}></div>
                                <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

                                <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-3xl sm:w-full sm:p-6">
                                    <div className="sm:flex sm:items-start">
                                        <div className="mt-3 text-center sm:mt-0 sm:text-left w-full">
                                            <div className="flex justify-between items-center mb-4">
                                                <h3 className="text-lg leading-6 font-medium text-gray-900" id="metadata-modal-title">
                                                    Dataset Details: {currentResult.name}
                                                </h3>
                                                <button onClick={() => setMetadataModalOpen(false)} className="text-gray-400 hover:text-gray-500">
                                                    <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                                    </svg>
                                                </button>
                                            </div>

                                            <div className="mt-2 space-y-4">
                                                <div className="grid grid-cols-2 gap-4 text-sm">
                                                    <div className="bg-gray-50 p-3 rounded">
                                                        <span className="block text-gray-500 text-xs uppercase">Process Time</span>
                                                        <span className="font-medium">{currentResult.metadata?.execution_time_seconds ? currentResult.metadata.execution_time_seconds.toFixed(2) + 's' : 'N/A'}</span>
                                                    </div>
                                                    <div className="bg-gray-50 p-3 rounded">
                                                        <span className="block text-gray-500 text-xs uppercase">Files Processed</span>
                                                        <span className="font-medium">{currentResult.metadata?.processed_count ?? 'N/A'}</span>
                                                    </div>
                                                </div>

                                                <div>
                                                    <h4 className="text-sm font-bold text-gray-900 mb-2">3-Shot Examples Used</h4>
                                                    <div className="bg-gray-50 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-48 overflow-y-auto border border-gray-200">
                                                        {currentResult.metadata?.examples_3_shot || "N/A"}
                                                    </div>
                                                </div>

                                                <div>
                                                    <h4 className="text-sm font-bold text-gray-900 mb-2">Constraints Used</h4>
                                                    <div className="bg-gray-50 p-3 rounded text-sm whitespace-pre-wrap max-h-48 overflow-y-auto border border-gray-200">
                                                        {currentResult.metadata?.formatted_constraints || "N/A"}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                                        <button
                                            type="button"
                                            onClick={() => setMetadataModalOpen(false)}
                                            className="w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:ml-3 sm:w-auto sm:text-sm"
                                        >
                                            Close
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )
                }
            </main >
        </div >
    );
};

export default RefBotPage;
