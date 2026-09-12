variable "cloud_id" {
  description = "ID облака Яндекс (yc config list)"
  type        = string
}

variable "folder_id" {
  description = "ID папки Яндекс (yc config list)"
  type        = string
}

variable "zone" {
  description = "Зона доступности"
  type        = string
  default     = "ru-central1-a"
}

variable "ubuntu_image_id" {
  description = "ID образа Ubuntu 22.04 (можно найти: yc compute image list --folder-id=standard-images)"
  type        = string
  default     = "fd8f2hfs5k5q1a4d8a3c"
}

variable "ssh_public_key" {
  description = "Публичный SSH-ключ (например, содержимое ~/.ssh/id_ed25519.pub)"
  type        = string
  sensitive   = true
}

variable "vm_name" {
  description = "Имя ВМ"
  type        = string
  default     = "alloy-mlops-vm"
}