import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';

function DropzoneLibrary({ onImageSelected, onImageCleared }) {
  const [selectedImage, setSelectedImage] = useState(null);
  const [inputResetKey, setInputResetKey] = useState(0);

  const processFile = useCallback(
    (file) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        setSelectedImage(event.target.result);
        onImageSelected(event.target.result, file);
      };
      reader.readAsDataURL(file);
    },
    [onImageSelected]
  );

  const onDrop = useCallback(
    (acceptedFiles, rejectedFiles) => {
      if (rejectedFiles.length > 0) {
        alert('Please upload a PNG or JPEG image');
        return;
      }

      if (acceptedFiles.length > 0) {
        processFile(acceptedFiles[0]);
      }
    },
    [processFile]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: {
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
    },
  });

  const handleClearImage = () => {
    setSelectedImage(null);
    setInputResetKey((currentKey) => currentKey + 1);
    onImageCleared?.();
  };

  const rootProps = getRootProps({
    className: `dropzone ${isDragActive ? 'active' : ''}`,
    role: 'button',
    tabIndex: 0,
  });

  const inputProps = getInputProps({
    capture: 'environment',
    className: 'file-input',
  });

  return (
    <div className="dropzone-container">
      {!selectedImage ? (
        <div {...rootProps}>
          <input key={inputResetKey} {...inputProps} />
          <div className="dropzone-content">
            <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <h3>Drop puzzle image here</h3>
            <p>or tap to choose from your device</p>
            <p className="file-info">PNG or JPEG • Phone camera supported</p>
          </div>
        </div>
      ) : (
        <div className="image-preview-container">
          <img src={selectedImage} alt="Selected sudoku" className="image-preview" />
          <button type="button" onClick={handleClearImage} className="clear-button">
            Upload Different Image
          </button>
        </div>
      )}
    </div>
  );
}

export default DropzoneLibrary;
