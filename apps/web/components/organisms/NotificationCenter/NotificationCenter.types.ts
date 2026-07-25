import type { Notification } from '@ambienta/shared';

export interface NotificationCenterProps {
  notifications: Notification[];
  onMarkAllAsRead: () => void;
}
