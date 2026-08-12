import { mockUsers } from '@/mocks/users';

export function getUserName(userId?: string): string {
  if (!userId) return 'Sin asignar';
  return mockUsers.find((u) => u.id === userId)?.nombre ?? 'Sin asignar';
}
