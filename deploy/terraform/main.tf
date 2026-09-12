terraform {
  required_version = ">= 1.5"

  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = "~> 0.129"
    }
  }
}

# Яндекс Облако — самый простой путь для бесплатного триала.
# Первый запуск:
#   1) yc init                    # войти в облако
#   2) yc config list             # посмотреть cloud_id / folder_id
#   3) terraform init && terraform plan && terraform apply
provider "yandex" {
  cloud_id  = var.cloud_id
  folder_id = var.folder_id
  zone      = var.zone
}

resource "yandex_vpc_network" "devops" {
  name = "alloy-mlops-net"
}

resource "yandex_vpc_subnet" "devops" {
  name           = "alloy-mlops-subnet"
  zone           = var.zone
  network_id     = yandex_vpc_network.devops.id
  v4_cidr_blocks = ["10.10.0.0/24"]
}

resource "yandex_compute_instance" "mlops" {
  name        = "alloy-mlops-vm"
  platform_id = "standard-v2"
  zone        = var.zone

  resources {
    cores  = 2
    memory = 4
  }

  boot_disk {
    initialize_params {
      image_id = var.ubuntu_image_id
      size     = 20
      type     = "network-hdd"
    }
  }

  network_interface {
    subnet_id          = yandex_vpc_subnet.devops.id
    nat                = true
    security_group_ids = [yandex_vpc_security_group.devops.id]
  }

  scheduling_policy {
    preemptible = true   # дешёвая подвижная ВМ для демо
  }

  metadata = {
    ssh-keys = "ubuntu:${var.ssh_public_key}"
  }
}

resource "yandex_vpc_security_group" "devops" {
  name       = "mlops-ingress"
  network_id = yandex_vpc_network.devops.id

  ingress {
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = ["0.0.0.0/0"]
    description    = "SSH"
  }
  ingress {
    protocol       = "TCP"
    port           = 3000
    v4_cidr_blocks = ["0.0.0.0/0"]
    description    = "Grafana"
  }
  ingress {
    protocol       = "TCP"
    port           = 8000
    v4_cidr_blocks = ["0.0.0.0/0"]
    description    = "ML API"
  }
}

output "vm_public_ip" {
  value = yandex_compute_instance.mlops.network_interface.0.nat_ip_address
}

output "vm_ssh" {
  value = "ssh ubuntu@${yandex_compute_instance.mlops.network_interface.0.nat_ip_address}"
}