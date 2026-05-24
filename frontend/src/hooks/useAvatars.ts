import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query'
import { avatarApi } from '@/services/api'
import { useNotificationStore } from '@/stores/notificationStore'
import type { CreateAvatarRequest, UpdateAvatarRequest, PaginationParams } from '@/types'

export const avatarKeys = {
  all: ['avatars'] as const,
  lists: () => [...avatarKeys.all, 'list'] as const,
  list: (params: PaginationParams) => [...avatarKeys.lists(), params] as const,
  details: () => [...avatarKeys.all, 'detail'] as const,
  detail: (id: string) => [...avatarKeys.details(), id] as const,
  public: () => [...avatarKeys.all, 'public'] as const,
}

export function useAvatars(params: PaginationParams = {}) {
  return useQuery({
    queryKey: avatarKeys.list(params),
    queryFn: () => avatarApi.list(params).then((r) => r.data),
    staleTime: 60_000,
  })
}

export function useInfiniteAvatars(params: Omit<PaginationParams, 'page'> = {}) {
  return useInfiniteQuery({
    queryKey: [...avatarKeys.lists(), 'infinite', params],
    queryFn: ({ pageParam = 1 }) =>
      avatarApi.list({ ...params, page: pageParam as number }).then((r) => r.data),
    getNextPageParam: (lastPage) =>
      lastPage.has_next ? lastPage.page + 1 : undefined,
    initialPageParam: 1,
  })
}

export function useAvatar(id: string) {
  return useQuery({
    queryKey: avatarKeys.detail(id),
    queryFn: () => avatarApi.get(id).then((r) => r.data),
    enabled: !!id,
    staleTime: 30_000,
  })
}

export function usePublicAvatars(params: PaginationParams = {}) {
  return useQuery({
    queryKey: [...avatarKeys.public(), params],
    queryFn: () => avatarApi.getPublic(params).then((r) => r.data),
    staleTime: 120_000,
  })
}

export function useCreateAvatar() {
  const queryClient = useQueryClient()
  const { success, error } = useNotificationStore()

  return useMutation({
    mutationFn: (data: CreateAvatarRequest) => avatarApi.create(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: avatarKeys.lists() })
      success('Avatar Created', 'Your avatar is being processed')
    },
    onError: (err: { message: string }) => {
      error('Creation Failed', err.message)
    },
  })
}

export function useUpdateAvatar() {
  const queryClient = useQueryClient()
  const { success, error } = useNotificationStore()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateAvatarRequest }) =>
      avatarApi.update(id, data).then((r) => r.data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: avatarKeys.lists() })
      queryClient.setQueryData(avatarKeys.detail(updated.id), updated)
      success('Avatar Updated', 'Changes saved successfully')
    },
    onError: (err: { message: string }) => {
      error('Update Failed', err.message)
    },
  })
}

export function useDeleteAvatar() {
  const queryClient = useQueryClient()
  const { success, error } = useNotificationStore()

  return useMutation({
    mutationFn: (id: string) => avatarApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: avatarKeys.lists() })
      success('Avatar Deleted', 'Avatar removed successfully')
    },
    onError: (err: { message: string }) => {
      error('Delete Failed', err.message)
    },
  })
}

export function useUploadAvatarSource() {
  const queryClient = useQueryClient()
  const { error } = useNotificationStore()

  return useMutation({
    mutationFn: ({
      id,
      formData,
      onProgress,
    }: {
      id: string
      formData: FormData
      onProgress?: (pct: number) => void
    }) => avatarApi.uploadSource(id, formData, onProgress).then((r) => r.data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: avatarKeys.lists() })
      queryClient.setQueryData(avatarKeys.detail(updated.id), updated)
    },
    onError: (err: { message: string }) => {
      error('Upload Failed', err.message)
    },
  })
}

export function useStartAvatarProcessing() {
  const queryClient = useQueryClient()
  const { success, error } = useNotificationStore()

  return useMutation({
    mutationFn: (id: string) => avatarApi.startProcessing(id).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: avatarKeys.lists() })
      success('Processing Started', 'Avatar processing has begun')
    },
    onError: (err: { message: string }) => {
      error('Processing Failed', err.message)
    },
  })
}
