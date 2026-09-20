import React from 'react';
import {
  TouchableOpacity,
  Text,
  StyleSheet,
  ActivityIndicator,
  ViewStyle,
} from 'react-native';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius, shadows } from '@theme/spacing';

interface HSAButtonProps {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'outline' | 'danger';
  size?: 'small' | 'medium' | 'large';
  loading?: boolean;
  disabled?: boolean;
  icon?: React.ReactNode;
  style?: ViewStyle;
}

export function HSAButton({
  title,
  onPress,
  variant = 'primary',
  size = 'medium',
  loading = false,
  disabled = false,
  icon,
  style,
}: HSAButtonProps) {
  const isDisabled = disabled || loading;
  const sizeStyles = {
    small: { paddingVertical: spacing.sm, paddingHorizontal: spacing.lg },
    medium: { paddingVertical: spacing.md, paddingHorizontal: spacing.xl },
    large: { paddingVertical: spacing.lg, paddingHorizontal: spacing.xxl },
  };

  const variantStyles = {
    primary: {
      backgroundColor: isDisabled ? colors.textLight : colors.hsaYellow,
      borderWidth: 0,
    },
    secondary: {
      backgroundColor: isDisabled ? colors.surfaceLight : colors.surface,
      borderWidth: 1,
      borderColor: colors.hsaYellow,
    },
    outline: {
      backgroundColor: 'transparent',
      borderWidth: 2,
      borderColor: isDisabled ? colors.textLight : colors.hsaYellow,
    },
    danger: {
      backgroundColor: isDisabled ? colors.textLight : colors.error,
      borderWidth: 0,
    },
  };

  const textColors = {
    primary: colors.hsaBlack,
    secondary: colors.hsaYellow,
    outline: colors.hsaYellow,
    danger: colors.textWhite,
  };

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={isDisabled}
      style={[
        styles.button,
        sizeStyles[size],
        variantStyles[variant],
        isDisabled && styles.disabled,
        style,
      ]}
      activeOpacity={0.8}
    >
      {loading ? (
        <ActivityIndicator color={textColors[variant]} size="small" />
      ) : (
        <>
          {icon}
          <Text
            style={[
              size === 'small' ? typography.buttonSmall : typography.button,
              { color: textColors[variant], textAlign: 'center' },
            ]}
          >
            {title}
          </Text>
        </>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    borderRadius: radius.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    ...shadows.small,
  },
  disabled: {
    opacity: 0.6,
  },
});
