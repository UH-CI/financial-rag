import React from 'react';

type StatuteRow = [string, string, string];

interface MatchingStatutesProps {
  data: StatuteRow[] | null; // Data can now be null
  onRowClick: (rowData: StatuteRow) => void;
}

export const MatchingStatutes: React.FC<MatchingStatutesProps> = ({ data, onRowClick }) => {
  if (data === null) {
    return (
      <div className="p-8 text-center border rounded-lg bg-gray-50 border-dashed border-gray-300">
        <p className="text-gray-500 font-medium">Please enter a search term</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border rounded-lg shadow-sm">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th scope="col" className="p-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Volume
            </th>
            <th scope="col" className="p-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Chapter
            </th>
            <th scope="col" className="p-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Section
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {data.map((row, index) => (
            <tr 
              key={index} 
              onClick={() => onRowClick(row)}
              className="hover:bg-blue-50 cursor-pointer transition-colors duration-150"
            >
              <td className="px-3 whitespace-nowrap text-sm text-gray-900 font-medium">
                {row[0]}
              </td>
              <td className="px-3 whitespace-nowrap text-sm text-gray-500">
                {row[1]}
              </td>
              <td className="px-3 whitespace-nowrap text-sm text-gray-500">
                {row[2]}
              </td>
            </tr>
          ))}
          
          {/* Optional: Handle case where data is [] (Search happened but found nothing) */}
          {data.length === 0 && (
            <tr>
              <td colSpan={3} className="px-3 py-8 text-center text-sm text-gray-500">
                No matching statutes found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};