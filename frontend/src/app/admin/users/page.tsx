"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listUsers, updateUser, deleteUser } from "@/lib/api/users";
import type { User } from "@/types/api";

export default function UsersPage() {
  const qc = useQueryClient();
  const { data: users = [], isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: listUsers,
  });

  const toggleEnabled = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      updateUser(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const remove = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  if (isLoading) return <div className="p-8 text-neutral-400">Loading…</div>;

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-white mb-6">Users</h1>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left text-neutral-300">
          <thead className="text-xs uppercase text-neutral-500 border-b border-neutral-700">
            <tr>
              <th className="pb-3 pr-4">Email</th>
              <th className="pb-3 pr-4">Username</th>
              <th className="pb-3 pr-4">Role</th>
              <th className="pb-3 pr-4">Status</th>
              <th className="pb-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800">
            {users.map((user: User) => (
              <tr key={user.id}>
                <td className="py-3 pr-4">{user.email}</td>
                <td className="py-3 pr-4">{user.username}</td>
                <td className="py-3 pr-4">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      user.role === "admin"
                        ? "bg-purple-900 text-purple-200"
                        : "bg-neutral-800 text-neutral-300"
                    }`}
                  >
                    {user.role}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <span
                    className={`px-2 py-0.5 rounded text-xs ${
                      user.enabled ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {user.enabled ? "Active" : "Disabled"}
                  </span>
                </td>
                <td className="py-3 flex gap-2">
                  <button
                    onClick={() =>
                      toggleEnabled.mutate({ id: user.id, enabled: !user.enabled })
                    }
                    className="text-xs text-blue-400 hover:text-blue-300"
                  >
                    {user.enabled ? "Disable" : "Enable"}
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Delete user ${user.email}?`)) remove.mutate(user.id);
                    }}
                    className="text-xs text-red-400 hover:text-red-300"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
