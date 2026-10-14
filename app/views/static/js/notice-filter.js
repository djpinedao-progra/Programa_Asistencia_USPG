(() => {
const noticeCourse = document.querySelector("[data-notice-course]");
const noticeStudent = document.querySelector("[data-notice-student]");
if (noticeCourse && noticeStudent) {
  const filterNoticeStudents = () => {
    const courseId = noticeCourse.value;
    [...noticeStudent.options].forEach((option) => {
      if (!option.value) return;
      option.hidden = Boolean(courseId && option.dataset.courseId !== courseId);
    });
    const selectedOption = noticeStudent.selectedOptions[0];
    if (selectedOption?.hidden) noticeStudent.value = "";
  };
  noticeCourse.addEventListener("change", filterNoticeStudents);
  filterNoticeStudents();
}


})();
