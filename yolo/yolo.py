from ultralytics import YOLO


def main():
    model = YOLO("yolov8n.pt")
    results = model("path/to/image.jpg")
    for r in results:
        print(r.boxes.data)


if __name__ == "__main__":
    main()
