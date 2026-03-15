"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { listUsers, createUser, updateUser, deleteUser } from "@/lib/api/users";
import type { User } from "@/types/api";

function CreateUserDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"user" | "admin">("user");

  const create = useMutation({
    mutationFn: () => createUser({ email, username, password, role }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setEmail("");
      setUsername("");
      setPassword("");
      setRole("user");
      onClose();
    },
  });

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5 w-full max-w-md space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--color-foreground)]">
            Create User
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-sm bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
          />
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-sm bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-sm bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as "user" | "admin")}
            className="w-full px-3 py-2 rounded-lg text-sm bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
          >
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>

          <button
            onClick={() => create.mutate()}
            disabled={!email.trim() || !username.trim() || !password.trim() || create.isPending}
            className="w-full px-3 py-2 rounded-lg text-sm font-medium bg-[hsl(217_91%_60%)] text-white hover:bg-[hsl(217_91%_55%)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {create.isPending ? "Creating..." : "Create User"}
          </button>
        </div>

        {create.isError && (
          <p className="text-xs text-red-400">
            {(create.error as Error)?.message || "Failed to create user"}
          </p>
        )}
      </div>
    </div>
  );
}

export default function UsersPage() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

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

  if (isLoading) return <div className="p-8 text-neutral-400">Loading...</div>;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Users</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-[hsl(217_91%_60%)] text-white hover:bg-[hsl(217_91%_55%)] transition-colors"
        >
          <Plus className="w-4 h-4" />
          Create User
        </button>
      </div>

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

      <CreateUserDialog open={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  );
}
